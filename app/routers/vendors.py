"""The public vendor directory: /vendors and /vendors/{slug}.

These pages exist to be found. Someone searching "stripe subprocessors"
wants the list; we have it, kept current by the same engine we sell. The
banner is the only ask on the page, and it is specific to the vendor being
read rather than a generic house ad.
"""
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.core.config import settings
from app.core.templating import templates as _templates
from app.db.models.vendor import Vendor, VendorChange
from app.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["vendors"])

# How many changes a vendor page shows. Long enough to establish that the
# page is genuinely watched, short enough to stay readable.
_CHANGE_LIMIT = 10


def _json_ld(vendor: Vendor, changes: list[VendorChange]) -> str:
    """Structured data for the vendor page.

    Modelled as a Dataset — that is what this is: a maintained, dated list
    about an organisation, with a stated update frequency. Claiming it were a
    Product or an Article would be describing it as something it is not.
    """
    base = settings.APP_URL.rstrip("/")
    url = f"{base}/vendors/{vendor.slug}"
    entries = vendor.entries or []
    graph: dict = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"{vendor.name} sub-processors",
        "description": (
            f"The sub-processors {vendor.name} publishes, with the change history "
            f"recorded since monitoring began. {len(entries)} entries."
        ),
        "url": url,
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


@router.get("/vendors", response_class=HTMLResponse)
async def vendor_index(request: Request, db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(
        select(Vendor).where(Vendor.is_published == True).order_by(Vendor.name)  # noqa: E712
    )
    vendors = list(result.scalars().all())
    return _templates.TemplateResponse(
        request, "vendors_index.html", {"vendors": vendors}
    )


@router.get("/vendors/{slug}", response_class=HTMLResponse)
async def vendor_page(
    request: Request, slug: str, db: AsyncSession = Depends(get_db_session)
):
    vendor = (
        await db.execute(
            select(Vendor).where(Vendor.slug == slug.lower(), Vendor.is_published == True)  # noqa: E712
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
        {
            "vendor": vendor,
            "entries": vendor.entries or [],
            "changes": changes,
            "json_ld": _json_ld(vendor, changes),
        },
    )
