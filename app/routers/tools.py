"""Public, no-signup growth tools. Unauthenticated by design — the whole
point is a visitor gets a result before deciding whether to sign up, so
every route here has to survive being pointed at an arbitrary URL or spammed
by a stranger: validate_url() for SSRF, a rate limiter for volume, and no
LLM call anywhere in the request path.
"""
import logging

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_grader import grade_for, scan_for_known_vendors
from app.core.ratelimit import SlidingWindowLimiter, get_client_ip
from app.core.scraper.fetcher import BotWallError, fetch_html_fast
from app.core.scraper.normalizer import HTMLNormalizer
from app.core.templating import templates as _templates
from app.core.urlguard import validate_url
from app.db.session import get_db_session
from app.services.evidence import evidence_zip
from app.services.leads import record_lead, sample_change_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tools"])

_normalizer = HTMLNormalizer()
# 5/min per IP: generous enough for someone re-checking after fixing their
# page, tight enough that this can't become a free open URL-fetch proxy.
_scan_limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60)
_zip_limiter = SlidingWindowLimiter(max_requests=5, window_seconds=60)


@router.get("/tools/audit-grader", response_class=HTMLResponse)
async def audit_grader_form(request: Request):
    return _templates.TemplateResponse(request, "audit_grader.html", {"result": None, "error": None})


@router.post("/tools/audit-grader", response_class=HTMLResponse)
async def audit_grader_scan(request: Request, url: str = Form(...)):
    client_ip = get_client_ip(request)
    if not _scan_limiter.allow(f"ip:{client_ip}"):
        return _templates.TemplateResponse(
            request,
            "audit_grader.html",
            {
                "result": None,
                "error": "Too many scans from this address — try again in a minute.",
                "submitted_url": url,
            },
            status_code=429,
        )

    try:
        await validate_url(url)
        html = await fetch_html_fast(url)
    except HTTPException as exc:
        return _templates.TemplateResponse(
            request,
            "audit_grader.html",
            {"result": None, "error": exc.detail, "submitted_url": url},
        )
    except BotWallError:
        return _templates.TemplateResponse(
            request,
            "audit_grader.html",
            {
                "result": None,
                "error": "That page blocks automated visitors, so we couldn't fetch it. Paste the privacy policy URL instead of the homepage, or try a different page.",
                "submitted_url": url,
            },
        )
    except httpx.HTTPError:
        return _templates.TemplateResponse(
            request,
            "audit_grader.html",
            {"result": None, "error": "Couldn't fetch that URL — check it's correct and publicly reachable.", "submitted_url": url},
        )
    except Exception:
        logger.exception("Audit grader scan failed for %s", url)
        return _templates.TemplateResponse(
            request,
            "audit_grader.html",
            {"result": None, "error": "Something went wrong reading that page. Try again in a moment.", "submitted_url": url},
        )

    text = _normalizer.normalize(html)
    if not text:
        return _templates.TemplateResponse(
            request,
            "audit_grader.html",
            {"result": None, "error": "That page came back empty — nothing to scan.", "submitted_url": url},
        )

    found = scan_for_known_vendors(text)
    grade, label = grade_for(len(found))
    logger.info("Audit grader: %s -> %d known vendor(s), grade %s", url, len(found), grade)

    return _templates.TemplateResponse(
        request,
        "audit_grader.html",
        {
            "result": {"found": found, "grade": grade, "label": label, "url": url},
            "error": None,
        },
    )


@router.post("/tools/sample-evidence-pack")
async def sample_evidence_pack(
    request: Request,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db_session),
):
    """The lead magnet: a real, downloadable audit ZIP built from fictional
    example data (no real tenant's evidence is ever handed out this way),
    so a visitor can see the actual file — SHA-256 anchor, raw HTML, diff,
    manifest — before creating an account."""
    client_ip = get_client_ip(request)
    if not _zip_limiter.allow(f"ip:{client_ip}") or not _zip_limiter.allow(f"email:{email.lower()}"):
        raise HTTPException(status_code=429, detail="Too many requests — try again in a minute.")

    await record_lead(email=email, source="sample_evidence_pack", context=None, session=db)

    zip_bytes = evidence_zip(sample_change_event(), "https://usetrustpages.com")
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="trustpages-sample-audit-evidence.zip"'},
    )
