"""The public vendor directory: /vendors and /vendors/{slug}-subprocessors.

These pages exist to be found. Someone searching "stripe subprocessors"
wants the list; we have it, kept current by the same engine we sell. The
banner is the only ask on the page, and it is specific to the vendor being
read rather than a generic house ad.

The canonical detail URL carries the `-subprocessors` suffix because that is
the phrase people search for. The bare `/vendors/stripe` form still works and
redirects there permanently — it was live and submitted to IndexNow before
the rename, and a 301 is what keeps that link equity.

The rendering functions are separate from the routes because the same pages
are served again under a language prefix by `routers.localized`.
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.i18n import DEFAULT_LANG, localized_path, page_context, translate
from app.core.templating import templates as _templates
from app.db.models.vendor import Vendor, VendorChange
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["vendors"])

# How many changes a vendor page shows. Long enough to establish that the
# page is genuinely watched, short enough to stay readable.
_CHANGE_LIMIT = 10

_SLUG_SUFFIX = "-subprocessors"


def vendor_path(lang: str, slug: str) -> str:
    return localized_path(lang, f"/vendors/{slug}{_SLUG_SUFFIX}")


def _json_ld(vendor: Vendor, changes: list[VendorChange], lang: str = DEFAULT_LANG) -> str:
    """Structured data for the vendor page.

    Modelled as a Dataset — that is what this is: a maintained, dated list
    about an organisation, with a stated update frequency. Claiming it were a
    Product or an Article would be describing it as something it is not.

    `inLanguage` and the localized name/description matter here: the same
    dataset is published in four languages at four URLs, and the markup has
    to agree with the page it sits on rather than describing the English one.
    """
    base = settings.APP_URL.rstrip("/")
    url = base + vendor_path(lang, vendor.slug)
    entries = vendor.entries or []
    graph: dict = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": translate(lang, "vendor.h1", vendor=vendor.name),
        "description": translate(lang, "vendor.meta_description", vendor=vendor.name),
        "url": url,
        "inLanguage": lang,
        "isAccessibleForFree": True,
        "creativeWorkStatus": "Published",
        "about": {
            "@type": "Organization",
            "name": vendor.name,
            **({"url": vendor.homepage_url} if vendor.homepage_url else {}),
        },
        "isBasedOn": vendor.monitored_url,
        "license": "https://usetrustpages.com/terms",
        "publisher": {"@type": "Organization", "name": "TrustPages", "url": base},
        "variableMeasured": [
            {"@type": "PropertyValue", "name": entry.get("name", "")}
            for entry in entries
            if entry.get("name")
        ],
    }
    if vendor.entries_updated_at:
        graph["dateModified"] = vendor.entries_updated_at.strftime("%Y-%m-%d")
    if changes:
        graph["temporalCoverage"] = (
            f"{changes[-1].created_at.strftime('%Y-%m-%d')}/"
            f"{changes[0].created_at.strftime('%Y-%m-%d')}"
        )
    return json.dumps(graph, ensure_ascii=False, indent=2)


async def published_vendors(db: AsyncSession) -> list[Vendor]:
    result = await db.execute(
        select(Vendor).where(Vendor.is_published == True).order_by(Vendor.name)  # noqa: E712
    )
    return list(result.scalars().all())


async def render_index(request: Request, lang: str, db: AsyncSession) -> HTMLResponse:
    vendors = await published_vendors(db)
    return _templates.TemplateResponse(
        request, "vendors_index.html", page_context(request, lang, vendors=vendors)
    )


async def render_detail(
    request: Request, lang: str, slug: str, db: AsyncSession
) -> HTMLResponse:
    """Serve one vendor page, or redirect the pre-rename URL to it."""
    slug = slug.lower()
    if not slug.endswith(_SLUG_SUFFIX):
        # `/vendors/stripe` → `/vendors/stripe-subprocessors`. Permanent: the
        # keyword-bearing URL is the canonical one now.
        return RedirectResponse(url=vendor_path(lang, slug), status_code=301)
    slug = slug[: -len(_SLUG_SUFFIX)]

    vendor = (
        await db.execute(
            select(Vendor).where(Vendor.slug == slug, Vendor.is_published == True)  # noqa: E712
        )
    ).scalar_one_or_none()
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    changes = list(
        (
            await db.execute(
                select(VendorChange)
                .where(VendorChange.vendor_id == vendor.id)
                .order_by(desc(VendorChange.created_at))
                .limit(_CHANGE_LIMIT)
            )
        ).scalars().all()
    )

    return _templates.TemplateResponse(
        request,
        "vendor_detail.html",
        page_context(
            request,
            lang,
            vendor=vendor,
            entries=vendor.entries or [],
            changes=changes,
            json_ld=_json_ld(vendor, changes, lang),
        ),
    )


@router.get("/vendors", response_class=HTMLResponse)
async def vendor_index(request: Request, db: AsyncSession = Depends(get_db_session)):
    return await render_index(request, DEFAULT_LANG, db)


@router.get("/vendors/{slug}", response_class=HTMLResponse)
async def vendor_page(
    request: Request, slug: str, db: AsyncSession = Depends(get_db_session)
):
    return await render_detail(request, DEFAULT_LANG, slug, db)
