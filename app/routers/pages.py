"""Public marketing/legal pages (no auth): landing, pricing, terms, privacy, refunds."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from app.core.config import settings
from app.core.templating import templates as _templates

router = APIRouter(tags=["pages"])

_STATIC_PATHS = ["/", "/pricing", "/terms", "/privacy", "/refunds"]


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
async def sitemap_xml():
    base = settings.APP_URL.rstrip("/")
    urls = "\n".join(
        f"  <url><loc>{base}{path}</loc></url>" for path in _STATIC_PATHS
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )
    return Response(content=xml, media_type="application/xml")
