"""Public marketing/legal pages (no auth): landing, pricing, terms, privacy, refunds."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.comparisons import (
    CATEGORIES,
    LEGACY_SLUGS,
    OUR_GAPS,
    OUR_POSITION,
    OURS,
    VERIFIED_ON,
)
from app.core.config import settings
from app.core.templating import templates as _templates
from app.db.models.vendor import Vendor
from app.db.session import get_db_session

router = APIRouter(tags=["pages"])

_STATIC_PATHS = ["/", "/pricing", "/compare", "/vendors", "/terms", "/privacy", "/refunds"]


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return _templates.TemplateResponse(request, "landing.html", {})


@router.get("/pricing", response_class=HTMLResponse)
async def pricing(request: Request):
    return _templates.TemplateResponse(request, "pricing.html", {})


@router.get("/terms", response_class=HTMLResponse)
async def terms(request: Request):
    return _templates.TemplateResponse(request, "terms.html", {})


@router.get("/privacy", response_class=HTMLResponse)
async def privacy(request: Request):
    return _templates.TemplateResponse(request, "privacy.html", {})


@router.get("/refunds", response_class=HTMLResponse)
async def refunds(request: Request):
    return _templates.TemplateResponse(request, "refunds.html", {})


@router.get("/compare", response_class=HTMLResponse)
async def compare(request: Request):
    """What a buyer meets when shopping this category, by shape rather than by
    name. Naming a competitor our own size on our own site advertises them to
    someone who had not heard of them; the categories carry the same
    information without doing that."""
    return _templates.TemplateResponse(
        request,
        "comparison.html",
        {
            "categories": CATEGORIES,
            "ours": OURS,
            "our_position": OUR_POSITION,
            "our_gaps": OUR_GAPS,
            "verified_on": VERIFIED_ON,
        },
    )


@router.get("/vs/{slug}")
async def comparison_redirect(slug: str):
    """The per-competitor pages this replaced were live and submitted to
    IndexNow, so they redirect rather than 404."""
    if slug.lower() not in LEGACY_SLUGS:
        raise HTTPException(status_code=404, detail="Not found")
    return RedirectResponse(url="/compare", status_code=301)


_INDEXNOW_KEY = "90b3cb9be9beb629e594522fb498dd60"


@router.get(f"/{_INDEXNOW_KEY}.txt", response_class=PlainTextResponse)
async def indexnow_key():
    # Verifies domain ownership for IndexNow (Bing/Yandex instant-indexing
    # ping) — no account needed, just this key file at the domain root.
    return _INDEXNOW_KEY


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    base = settings.APP_URL.rstrip("/")
    return f"User-agent: *\nAllow: /\nDisallow: /dashboard\nDisallow: /admin\n\nSitemap: {base}/sitemap.xml\n"


@router.get("/sitemap.xml")
async def sitemap_xml(db: AsyncSession = Depends(get_db_session)):
    base = settings.APP_URL.rstrip("/")
    # Directory pages are most of the reason to have a sitemap at all: there
    # are more of them than of everything else together, and they change.
    published = (
        await db.execute(
            select(Vendor.slug, Vendor.entries_updated_at)
            .where(Vendor.is_published == True)  # noqa: E712
            .order_by(Vendor.slug)
        )
    ).all()

    lines = [f"  <url><loc>{base}{path}</loc></url>" for path in _STATIC_PATHS]
    for slug, updated_at in published:
        lastmod = (
            f"<lastmod>{updated_at.strftime('%Y-%m-%d')}</lastmod>" if updated_at else ""
        )
        lines.append(f"  <url><loc>{base}/vendors/{slug}</loc>{lastmod}</url>")
    urls = "\n".join(lines)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )
    return Response(content=xml, media_type="application/xml")
