"""The `/de`, `/fr` and `/es` mirror of every public page.

This router is registered LAST, on purpose. Its paths start with `/{lang}`,
which would otherwise shadow every one-segment route in the app — `/vendors`,
`/pricing`, `/healthz` — and answer them with a 404 for "vendors is not a
language". Registered last, FastAPI has already matched the real routes and
only genuinely unclaimed paths reach here.

`/en/...` is not served: English lives at the root, and a second URL with
identical text is the one i18n mistake that reliably costs rankings. It
redirects permanently instead, so an /en link someone wrote by hand still
works.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.comparisons import LEGACY_SLUGS
from app.core.i18n import DEFAULT_LANG, SUPPORTED_LANGS, localized_path
from app.db.session import get_db_session
from app.routers import vendors as vendors_router
from app.routers.pages import _remember_language, render_compare, render_landing, render_pricing

logger = logging.getLogger(__name__)

router = APIRouter(tags=["i18n"])

# Everything except English, which is the root.
PREFIXED_LANGS = tuple(code for code in SUPPORTED_LANGS if code != DEFAULT_LANG)


def _check(lang: str) -> str:
    """404 for anything that is not a language we publish.

    Deliberately not a redirect to English: `/kk/pricing` is not a page that
    moved, it is a page that never existed, and telling a crawler otherwise
    invents an infinite URL space.
    """
    if lang not in PREFIXED_LANGS:
        raise HTTPException(status_code=404, detail="Not found")
    return lang


# ── /en/... → the root, permanently ─────────────────────────────────────────

@router.get("/en")
async def english_root():
    return RedirectResponse(url="/", status_code=301)


@router.get("/en/{rest:path}")
async def english_prefix(rest: str):
    return RedirectResponse(url="/" + rest.lstrip("/"), status_code=301)


# ── the localized pages ─────────────────────────────────────────────────────

@router.get("/{lang}", response_class=HTMLResponse)
async def landing(request: Request, lang: str):
    return _remember_language(render_landing(request, _check(lang)), lang)


@router.get("/{lang}/pricing", response_class=HTMLResponse)
async def pricing(request: Request, lang: str):
    return _remember_language(render_pricing(request, _check(lang)), lang)


@router.get("/{lang}/compare", response_class=HTMLResponse)
async def compare(request: Request, lang: str):
    return _remember_language(render_compare(request, _check(lang)), lang)


@router.get("/{lang}/vendors", response_class=HTMLResponse)
async def vendor_index(
    request: Request, lang: str, db: AsyncSession = Depends(get_db_session)
):
    return _remember_language(
        await vendors_router.render_index(request, _check(lang), db), lang
    )


@router.get("/{lang}/vendors/{slug}", response_class=HTMLResponse)
async def vendor_page(
    request: Request, lang: str, slug: str, db: AsyncSession = Depends(get_db_session)
):
    response = await vendors_router.render_detail(request, _check(lang), slug, db)
    # A redirect to the canonical slug must not also plant a cookie for a
    # page the visitor has not actually landed on yet.
    if isinstance(response, RedirectResponse):
        return response
    return _remember_language(response, lang)


@router.get("/{lang}/vs/{slug}")
async def comparison_redirect(lang: str, slug: str):
    if slug.lower() not in LEGACY_SLUGS:
        raise HTTPException(status_code=404, detail="Not found")
    return RedirectResponse(url=localized_path(_check(lang), "/compare"), status_code=301)


# The legal pages exist in English only — they are the contract. A localized
# link to them lands on the English original rather than on a 404.
@router.get("/{lang}/terms")
@router.get("/{lang}/privacy")
@router.get("/{lang}/refunds")
async def legal_redirect(request: Request, lang: str):
    _check(lang)
    _, _, tail = request.url.path.strip("/").partition("/")
    return RedirectResponse(url=f"/{tail}", status_code=301)
