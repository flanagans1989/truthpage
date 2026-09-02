"""The catalogues themselves, and the URL algebra around them."""
import json
from datetime import datetime
from pathlib import Path

import pytest

from app.core.i18n import (
    DEFAULT_LANG,
    SUPPORTED_LANGS,
    alternates,
    format_date,
    is_crawler,
    localized_path,
    normalise_lang,
    preferred_language,
    strip_lang_prefix,
    translate,
)

LOCALES = Path(__file__).parent.parent / "locales"


def _catalog(lang: str) -> dict:
    return json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))


class TestCatalogues:
    def test_every_supported_language_has_a_file(self):
        for lang in SUPPORTED_LANGS:
            assert (LOCALES / f"{lang}.json").exists(), lang

    @pytest.mark.parametrize("lang", [l for l in SUPPORTED_LANGS if l != DEFAULT_LANG])
    def test_no_key_is_missing_against_english(self, lang):
        # A missing key silently falls back to English mid-paragraph. The
        # fallback is there for safety, not as a translation strategy.
        missing = set(_catalog(DEFAULT_LANG)) - set(_catalog(lang))
        assert not missing, f"{lang} is missing: {sorted(missing)}"

    @pytest.mark.parametrize("lang", SUPPORTED_LANGS)
    def test_no_key_is_left_empty(self, lang):
        blank = [k for k, v in _catalog(lang).items() if isinstance(v, str) and not v.strip()]
        # footer.legal_note is intentionally empty in English: there is no
        # note to make when the page and the contract are the same language.
        assert blank == [] or blank == ["footer.legal_note"], blank

    @pytest.mark.parametrize("lang", SUPPORTED_LANGS)
    def test_placeholders_survive_translation(self, lang):
        """A translated string that dropped its {vendor} renders a sentence
        with a hole in it; one that invented a new placeholder raises."""
        english = _catalog(DEFAULT_LANG)
        for key, value in _catalog(lang).items():
            if not isinstance(value, str) or not isinstance(english.get(key), str):
                continue
            import re

            expected = set(re.findall(r"\{(\w+)\}", english[key]))
            actual = set(re.findall(r"\{(\w+)\}", value))
            assert actual == expected, f"{lang}:{key} expected {expected}, got {actual}"

    @pytest.mark.parametrize("lang", SUPPORTED_LANGS)
    def test_compare_categories_keep_their_shape(self, lang):
        cats = _catalog(lang)["compare.categories"]
        assert [c["slug"] for c in cats] == [c["slug"] for c in _catalog(DEFAULT_LANG)["compare.categories"]]
        for c in cats:
            assert c["name"] and c["shape"] and c["price"] and c["pick_them_when"]
            assert len(c["strengths"]) == 3 and len(c["limits"]) == 3


class TestLocalTerminology:
    """The point of translating at all: a German buyer searches for
    Unterauftragsverarbeiter, not for a rendering of "sub-processor"."""

    def test_german_uses_the_regulatory_vocabulary(self):
        blob = json.dumps(_catalog("de"), ensure_ascii=False)
        assert "Unterauftragsverarbeiter" in blob
        assert "DSGVO" in blob
        assert "AVV" in blob
        assert "GDPR" not in blob

    def test_french_uses_the_regulatory_vocabulary(self):
        blob = json.dumps(_catalog("fr"), ensure_ascii=False)
        assert "sous-traitants ultérieurs" in blob
        assert "RGPD" in blob
        assert "GDPR" not in blob

    def test_spanish_uses_the_regulatory_vocabulary(self):
        blob = json.dumps(_catalog("es"), ensure_ascii=False)
        assert "subencargado" in blob
        assert "RGPD" in blob
        assert "GDPR" not in blob

    def test_german_landing_title_carries_the_search_term(self):
        title = translate("de", "landing.meta_title")
        assert "Unterauftragsverarbeiter" in title and "DSGVO" in title
        # Long titles get truncated in the result page; keep it inside the
        # width Google actually renders.
        assert len(title) <= 90, len(title)


class TestTranslate:
    def test_interpolates_parameters(self):
        assert "Stripe" in translate("de", "vendor.h1", vendor="Stripe")

    def test_falls_back_to_english_for_an_unknown_key(self):
        assert translate("de", "no.such.key.anywhere") == "no.such.key.anywhere"

    def test_returns_lists_untouched(self):
        assert isinstance(translate("fr", "compare.gaps"), list)


class TestUrlAlgebra:
    def test_english_stays_at_the_root(self):
        assert localized_path("en", "/pricing") == "/pricing"
        assert localized_path("en", "/") == "/"

    def test_other_languages_get_a_prefix(self):
        assert localized_path("de", "/pricing") == "/de/pricing"
        assert localized_path("fr", "/") == "/fr"
        assert localized_path("es", "/vendors/stripe-subprocessors") == "/es/vendors/stripe-subprocessors"

    def test_stripping_is_the_inverse(self):
        for lang in SUPPORTED_LANGS:
            for path in ("/", "/pricing", "/vendors/stripe-subprocessors"):
                assert strip_lang_prefix(localized_path(lang, path)) == (lang, path)

    def test_a_path_segment_that_looks_like_a_language_is_only_stripped_when_it_is_one(self):
        assert strip_lang_prefix("/vendors/es") == ("en", "/vendors/es")

    def test_alternates_cover_every_language_plus_x_default(self):
        links = alternates("/de/pricing", "https://example.com")
        assert [l["hreflang"] for l in links] == list(SUPPORTED_LANGS) + ["x-default"]
        assert links[-1]["href"] == "https://example.com/pricing"

    def test_alternates_are_reciprocal(self):
        # Whichever language you start from, the set is identical — the
        # condition search engines require before honouring hreflang at all.
        assert alternates("/fr/vendors", "https://x.io") == alternates("/vendors", "https://x.io")

    def test_unknown_language_falls_back_rather_than_404ing_the_helper(self):
        assert normalise_lang("kk") == "en"
        assert normalise_lang(None) == "en"


class TestAcceptLanguage:
    @pytest.mark.parametrize(
        "header,expected",
        [
            ("de-DE,de;q=0.9,en;q=0.8", "de"),
            ("fr-CA,fr;q=0.9", "fr"),
            ("es", "es"),
            ("en-GB,en;q=0.9", "en"),
            # q values decide, not order in the string
            ("de;q=0.2,en;q=0.9", "en"),
            ("tr-TR,tr;q=0.9", None),
            ("*", None),
            ("", None),
            (None, None),
        ],
    )
    def test_picks_the_best_supported_language(self, header, expected):
        assert preferred_language(header) == expected

    def test_a_malformed_q_value_does_not_raise(self):
        assert preferred_language("de;q=banana,en") == "en"


class TestCrawlerDetection:
    @pytest.mark.parametrize(
        "ua",
        [
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Mozilla/5.0 (compatible; bingbot/2.0)",
            "Mozilla/5.0 (compatible; YandexBot/3.0)",
            "facebookexternalhit/1.1",
        ],
    )
    def test_known_crawlers_are_never_redirected(self, ua):
        assert is_crawler(ua)

    def test_a_browser_is_not_a_crawler(self):
        assert not is_crawler(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
        )


class TestDateFormatting:
    def test_each_market_gets_the_format_it_reads(self):
        when = datetime(2026, 9, 2)
        assert format_date("de", when) == "02.09.2026"
        assert format_date("fr", when) == "02/09/2026"
        assert format_date("es", when) == "02/09/2026"
        assert format_date("en", when) == "02 Sep 2026"

    def test_missing_dates_render_as_nothing_rather_than_none(self):
        assert format_date("de", None) == ""
