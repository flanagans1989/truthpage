"""Public marketing/legal pages (no auth): landing, pricing, compare, legal.

English lives here at the root. The same pages under `/de`, `/fr` and `/es`
are registered by `routers.localized`, which calls the same render functions
with a different language — one template, one set of copy decisions, four
URLs.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.comparisons import LEGACY_SLUGS, OURS, VERIFIED_ON
from app.core.config import settings
from app.core.i18n import (
    DEFAULT_LANG,
    SUPPORTED_LANGS,
    is_crawler,
    localized_path,
    page_context,
    preferred_language,
    translate,
)
from app.core.templating import templates as _templates
from app.db.models.vendor import Vendor
from app.db.session import get_db_session

# Legal texts are binding in English only (see footer.legal_note), so they
# are listed in the sitemap once, without hreflang alternates. Kept as one
# tuple because the sitemap test counts against it.
ENGLISH_ONLY_LEGAL_PATHS = ("/terms", "/privacy", "/refunds", "/dpa")

router = APIRouter(tags=["pages"])

# Localized static pages. The legal three are deliberately not here: they are
# the contract, and a translated contract raises the question of which
# version governs. The localized footer links to the English originals.
_LOCALIZED_PATHS = ["/", "/pricing", "/compare", "/vendors"]

# Where a language cookie is remembered once the visitor has been anywhere
# with an explicit prefix.
_LANG_COOKIE = "lang"


# ── render functions, shared with routers.localized ──────────────────────────

def render_landing(request: Request, lang: str) -> HTMLResponse:
    return _templates.TemplateResponse(request, "landing.html", page_context(request, lang))


def render_pricing(request: Request, lang: str) -> HTMLResponse:
    return _templates.TemplateResponse(request, "pricing.html", page_context(request, lang))


def render_compare(request: Request, lang: str) -> HTMLResponse:
    """What a buyer meets when shopping this category, by shape rather than by
    name. Naming a competitor our own size on our own site advertises them to
    someone who had not heard of them; the categories carry the same
    information without doing that — in every language."""
    return _templates.TemplateResponse(
        request,
        "comparison.html",
        page_context(
            request,
            lang,
            categories=translate(lang, "compare.categories"),
            our_position=translate(lang, "compare.position"),
            our_gaps=translate(lang, "compare.gaps"),
            ours=OURS,
            verified_on=VERIFIED_ON,
        ),
    )


# ── English routes at the root ───────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def landing(
    request: Request,
    accept_language: str | None = Header(default=None),
    user_agent: str | None = Header(default=None),
):
    """The English landing page, or a nudge to the visitor's own language.

    The redirect happens on the root only, never on a deep link, never for a
    crawler, and never once the visitor has been to a prefixed URL — the
    cookie their language choice leaves behind is what stops it. A visitor
    who wants English can always click EN, which puts them back here with
    the cookie set.
    """
    if request.cookies.get(_LANG_COOKIE) is None and not is_crawler(user_agent):
        guess = preferred_language(accept_language)
        if guess and guess != DEFAULT_LANG:
            return RedirectResponse(url=f"/{guess}", status_code=302)
    return _remember_language(render_landing(request, DEFAULT_LANG), DEFAULT_LANG)


@router.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    return render_pricing(request, DEFAULT_LANG)


@router.get("/compare", response_class=HTMLResponse)
async def compare(request: Request):
    return render_compare(request, DEFAULT_LANG)


@router.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    return _templates.TemplateResponse(request, "terms.html", {})


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return _templates.TemplateResponse(request, "privacy.html", {})


@router.get("/refunds", response_class=HTMLResponse)
async def refunds(request: Request):
    return _templates.TemplateResponse(request, "refunds.html", {})


@router.get("/dpa", response_class=HTMLResponse)
async def dpa(request: Request):
    """Article 28(3) terms, published rather than sent on request.

    We process subscriber and notice-recipient addresses on our customers'
    behalf, which makes us their processor — so a DPA is not optional, and
    a buyer's security review asks for one before anything else. Selling
    the ability to answer that review without being able to answer it
    ourselves was the sharpest contradiction on the site.
    """
    return _templates.TemplateResponse(request, "dpa.html", {})


@router.get("/vs/{slug}")
async def comparison_redirect(slug: str):
    """The per-competitor pages this replaced were live and submitted to
    IndexNow, so they redirect rather than 404."""
    if slug.lower() not in LEGACY_SLUGS:
        raise HTTPException(status_code=404, detail="Not found")
    return RedirectResponse(url="/compare", status_code=301)


def _remember_language(response, lang: str):
    """Remember an explicit language so the root stops guessing.

    Set on every localized page view, not only on a click in the switcher:
    arriving on /de from a German search result is as clear a signal as
    picking Deutsch from the menu.
    """
    response.set_cookie(
        key=_LANG_COOKIE,
        value=lang,
        max_age=60 * 60 * 24 * 365,
        httponly=False,
        samesite="lax",
        secure=settings.APP_URL.startswith("https"),
    )
    return response


_INDEXNOW_KEY = "90b3cb9be9beb629e594522fb498dd60"


@router.get(f"/{_INDEXNOW_KEY}.txt", response_class=PlainTextResponse)
async def indexnow_key():
    # Verifies domain ownership for IndexNow (Bing/Yandex instant-indexing
    # ping) — no account needed, just this key file at the domain root.
    return _INDEXNOW_KEY


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    base = settings.APP_URL.rstrip("/")
    return f"User-agent: *\nAllow: /\nDisallow: /dashboard\nDisallow: /onboarding\nDisallow: /admin\n\nSitemap: {base}/sitemap.xml\n"


@router.get("/sitemap.xml")
async def sitemap_xml(db: AsyncSession = Depends(get_db_session)):
    """Every page in every language, each carrying the full alternate set.

    A sitemap that lists only the English URLs tells a search engine the
    other three do not exist; listing them without the `xhtml:link`
    alternates tells it they are unrelated pages that happen to look alike.
    Both are the same lost ranking, so the alternates are the point of this
    file rather than a decoration on it.
    """
    base = settings.APP_URL.rstrip("/")
    published = (
        await db.execute(
            select(Vendor.slug, Vendor.entries_updated_at)
            .where(Vendor.is_published == True)  # noqa: E712
            .order_by(Vendor.slug)
        )
    ).all()

    # (bare path, lastmod or None) — bare meaning "without a language prefix".
    pages: list[tuple[str, str | None]] = [(path, None) for path in _LOCALIZED_PATHS]
    for slug, updated_at in published:
        lastmod = updated_at.strftime("%Y-%m-%d") if updated_at else None
        pages.append((f"/vendors/{slug}-subprocessors", lastmod))

    lines: list[str] = []
    for bare, lastmod in pages:
        alt_lines = [
            f'    <xhtml:link rel="alternate" hreflang="{code}" '
            f'href="{base}{localized_path(code, bare)}"/>'
            for code in SUPPORTED_LANGS
        ]
        alt_lines.append(
            '    <xhtml:link rel="alternate" hreflang="x-default" '
            f'href="{base}{localized_path(DEFAULT_LANG, bare)}"/>'
        )
        for code in SUPPORTED_LANGS:
            lines.append("  <url>")
            lines.append(f"    <loc>{base}{localized_path(code, bare)}</loc>")
            if lastmod:
                lines.append(f"    <lastmod>{lastmod}</lastmod>")
            lines.extend(alt_lines)
            lines.append("  </url>")

    # The English-only legal pages, listed once with no alternates.
    for path in ENGLISH_ONLY_LEGAL_PATHS:
        lines.append(f"  <url><loc>{base}{path}</loc></url>")

    body = "\n".join(lines)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        f"{body}\n"
        "</urlset>\n"
    )
    return Response(content=xml, media_type="application/xml")
