"""Four languages, one set of templates.

Structure: English lives at the root (`/pricing`), every other language under
its own prefix (`/de/pricing`). `/en/...` is not a second home for the English
pages — it redirects to the root, because two URLs serving identical text is
the one i18n mistake that actually costs rankings.

Translations are flat dotted keys in `locales/<lang>.json`. A missing key
falls back to English and logs: a page with a hole in it is worse than a page
with one English sentence on it, and the log is how the hole gets found.

Terminology is the point of this file, not decoration. A German buyer
searches for "Unterauftragsverarbeiter" and "AVV", not for a translation of
"sub-processor" and "DPA"; a French one for "sous-traitants ultérieurs" and
"RGPD". The locale files use the regulatory vocabulary of each market, which
is also what the keyword volume sits on.
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_LANG = "en"
# Order matters: it is the order of the language menu and of the hreflang tags.
SUPPORTED_LANGS = ("en", "de", "fr", "es")

# Shown in the switcher. Endonyms — a German speaker looks for "Deutsch",
# not for "German".
LANG_NAMES = {"en": "English", "de": "Deutsch", "fr": "Français", "es": "Español"}
LANG_SHORT = {"en": "EN", "de": "DE", "fr": "FR", "es": "ES"}

# Numeric where the market writes numbers. "01 Sep 2026" is unreadable to a
# German reader and month names would have to be translated by hand anyway.
DATE_FORMATS = {"en": "%d %b %Y", "de": "%d.%m.%Y", "fr": "%d/%m/%Y", "es": "%d/%m/%Y"}


def format_date(lang: str, value) -> str:
    if value is None:
        return ""
    return value.strftime(DATE_FORMATS.get(lang, DATE_FORMATS[DEFAULT_LANG]))

_LOCALES_DIR = Path(__file__).parent.parent.parent / "locales"

# Set once a missing key has been reported, so a hot path cannot spam the log
# with the same line thousands of times.
_reported_missing: set[str] = set()


@lru_cache(maxsize=None)
def _catalog(lang: str) -> dict:
    path = _LOCALES_DIR / f"{lang}.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def translate(lang: str, key: str, **params) -> str:
    """One string. Falls back to English, then to the key itself.

    Returning the key rather than an empty string is deliberate: a page that
    renders `pricing.cta` in the middle of a sentence is obviously broken,
    while a silent blank looks like an intentional design.
    """
    value = _catalog(lang).get(key)
    if value is None:
        value = _catalog(DEFAULT_LANG).get(key)
        if key not in _reported_missing:
            _reported_missing.add(key)
            logger.warning("i18n: missing key '%s' for language '%s'", key, lang)
    if value is None:
        return key
    if params and isinstance(value, str):
        try:
            return value.format(**params)
        except (KeyError, IndexError):
            logger.warning("i18n: bad interpolation for '%s' (%s)", key, lang)
            return value
    return value


def translator(lang: str):
    """The `t` callable handed to templates."""

    def _t(key: str, **params):
        return translate(lang, key, **params)

    return _t


def normalise_lang(lang: str | None) -> str:
    lang = (lang or "").lower().strip()
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def localized_path(lang: str, path: str) -> str:
    """`/pricing` in German is `/de/pricing`; in English it stays `/pricing`."""
    path = "/" + path.strip("/")
    if lang == DEFAULT_LANG:
        return path if path != "/" else "/"
    return f"/{lang}" if path == "/" else f"/{lang}{path}"


def strip_lang_prefix(path: str) -> tuple[str, str]:
    """Split "/de/vendors/stripe" into ("de", "/vendors/stripe")."""
    parts = path.strip("/").split("/", 1)
    if parts and parts[0] in SUPPORTED_LANGS:
        rest = "/" + parts[1] if len(parts) > 1 else "/"
        return parts[0], rest
    return DEFAULT_LANG, "/" + path.strip("/")


def alternates(path: str, app_url: str) -> list[dict[str, str]]:
    """The hreflang set for one page, x-default included.

    x-default points at the English root rather than at a language-picker
    page: there is no picker, and pointing it at a page that does not exist
    is how x-default usually gets wrong.
    """
    base = app_url.rstrip("/")
    _, bare = strip_lang_prefix(path)
    links = [
        {"hreflang": lang, "href": base + localized_path(lang, bare)}
        for lang in SUPPORTED_LANGS
    ]
    links.append({"hreflang": "x-default", "href": base + localized_path(DEFAULT_LANG, bare)})
    return links


def preferred_language(accept_language: str | None) -> str | None:
    """Best supported match for an Accept-Language header, or None.

    None means "no opinion" — the caller then leaves the visitor on English
    rather than guessing. Quality values are honoured because browsers do
    send them, and "de;q=0.2, en;q=0.9" means English.
    """
    if not accept_language:
        return None

    ranked: list[tuple[float, int, str]] = []
    for index, part in enumerate(accept_language.split(",")):
        piece = part.strip()
        if not piece:
            continue
        tag, _, params = piece.partition(";")
        quality = 1.0
        for param in params.split(";"):
            name, _, value = param.strip().partition("=")
            if name.strip() == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
        # index keeps the header's own order stable among equal q values
        ranked.append((-quality, index, tag.strip().lower()))

    for _, _, tag in sorted(ranked):
        if tag == "*":
            continue
        primary = tag.split("-")[0]
        if primary in SUPPORTED_LANGS:
            return primary
    return None


# Crawlers must see the language they asked for. Google crawls mostly from the
# US with no Accept-Language, so a redirect would be harmless for it — but
# some crawlers do send one, and a bot bounced to /de will index /de's content
# under the English URL. Cheap to exclude, expensive to get wrong.
_BOT_MARKERS = (
    "bot", "crawler", "spider", "slurp", "bingpreview", "facebookexternalhit",
    "embedly", "quora link preview", "whatsapp", "telegrambot", "applebot",
)


def is_crawler(user_agent: str | None) -> bool:
    ua = (user_agent or "").lower()
    return any(marker in ua for marker in _BOT_MARKERS)


def page_context(request, lang: str, **extra) -> dict:
    """Everything a public template needs to render itself in one language.

    `u` is the link helper: templates write `u("/pricing")` and get
    `/de/pricing` or `/pricing` depending on where they are, so no template
    has to know about the prefix scheme.
    """
    from app.core.config import settings

    app_url = settings.APP_URL.rstrip("/")
    _, bare = strip_lang_prefix(request.url.path)

    context = {
        "lang": lang,
        "t": translator(lang),
        "u": lambda path: localized_path(lang, path),
        "d": lambda value: format_date(lang, value),
        "alternates": alternates(request.url.path, app_url),
        "canonical_url": app_url + localized_path(lang, bare),
        "languages": [
            {
                "code": code,
                "name": LANG_NAMES[code],
                "short": LANG_SHORT[code],
                "href": localized_path(code, bare),
                "current": code == lang,
            }
            for code in SUPPORTED_LANGS
        ],
    }
    context.update(extra)
    return context
