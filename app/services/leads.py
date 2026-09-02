"""Lead capture for the public growth tools, and the fictional example
event behind the sample evidence ZIP.

See app.db.models.lead.Lead for why a lead is its own table rather than a
passwordless Tenant.
"""
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.tsa import parse_reply
from app.db.models.lead import Lead

# A REAL RFC 3161 token, fetched once from FreeTSA for this fixed example's
# digest (not a fake/placeholder .tsr) — the sample ZIP's whole pitch is
# "verify this yourself", so it has to hold up to verify.sh actually being
# run against it. Getting a fresh token for a fictional, unchanging digest
# is not backdating: there is no real capture event here to misrepresent —
# see KURAL 0 in docs/manifest_v2.md, which is about never doing this for
# an actual monitored change.
_SAMPLE_TSR_PATH = Path(__file__).parent.parent / "static_data" / "sample" / "sample-after-html.sha256.tsr"


async def record_lead(
    *, email: str, source: str, context: str | None, session: AsyncSession
) -> None:
    lead = Lead(email=email.strip().lower(), source=source, context=context)
    session.add(lead)
    await session.commit()


def sample_tenant() -> SimpleNamespace:
    """The fictional tenant behind the sample ZIP — pairs with
    sample_change_event() below, same never-real-data reasoning."""
    return SimpleNamespace(name="Example SaaS Inc.", slug="example-saas")


def sample_change_event() -> SimpleNamespace:
    """A fictional change, shaped exactly like a real ChangeEvent, for the
    downloadable sample ZIP. Never real tenant data: a made-up company's
    made-up notice about a real vendor's (Stripe's) publicly documented
    sub-processor page, so the sample reads as plausible without
    describing any actual customer or event.
    """
    now = datetime.now(UTC)
    subprocessor = SimpleNamespace(
        name="Stripe",
        monitored_url="https://stripe.com/legal/service-providers",
    )
    return SimpleNamespace(
        id=uuid4(),
        subprocessor=subprocessor,
        created_at=now,
        llm_classification="MATERIAL",
        llm_confidence=0.94,
        llm_summary=(
            "Stripe added a new sub-processor, Example Cloud Services Inc. "
            "(United States), for payment fraud analysis."
        ),
        status="approved",
        # Actually computed sha256() of old_content_text/new_content_text
        # below — not decorative placeholders, so a visitor who hashes the
        # extracted files themselves gets a match.
        old_hash="b7b3eadd213817bebda3e4f92eaf9d540e3a938a94c94c9ebec0dfad4fc6b1fc",
        new_hash="22e453500c955d89e1e5a00622fdd68ae8f921554f57f088d0d808f61b8d4d89",
        approved_by="sample@example.com",
        approved_at=now,
        notified_at=now,
        notice_subject="Update to our sub-processor list",
        notice_body=(
            "Hi,\n\n"
            "We're writing to let you know that one of our vendors, Stripe, has added a "
            "new sub-processor: Example Cloud Services Inc., based in the United States, "
            "used for payment fraud analysis.\n\n"
            "Under our agreement with you, you have [OBJECTION WINDOW] days from this "
            "notice to object to this change. If you have any questions, please contact "
            "[CONTACT].\n\n"
            "Best regards,\nThe Team"
        ),
        old_content_text=(
            "Sub-processors: AWS (hosting, United States), Cloudflare (CDN, United States)."
        ),
        new_content_text=(
            "Sub-processors: AWS (hosting, United States), Cloudflare (CDN, United States), "
            "Example Cloud Services Inc. (payment fraud analysis, United States)."
        ),
        old_raw_html="<html><body><p>Sub-processors: AWS, Cloudflare.</p></body></html>",
        new_raw_html=(
            "<html><body><p>Sub-processors: AWS, Cloudflare, "
            "Example Cloud Services Inc.</p></body></html>"
        ),
        # Actually sha256() of old_raw_html/new_raw_html below — see note
        # on old_hash/new_hash above.
        old_raw_html_hash="1ebb60acfc4f8594a25522be9e7b8ab93e8e4f95a6b60e437b1ca8cdb255095d",
        new_raw_html_hash="271a879deb5a0d25f45792bab8a7e911b19a8d611dd4c3ce4adc397dea3b5101",
        raw_diff=(
            "--- before\n+++ after\n"
            "@@ -1 +1 @@\n"
            "-Sub-processors: AWS (hosting, United States), Cloudflare (CDN, United States).\n"
            "+Sub-processors: AWS (hosting, United States), Cloudflare (CDN, United States), "
            "Example Cloud Services Inc. (payment fraud analysis, United States).\n"
        ),
        **_sample_timestamp_fields(),
    )


def _sample_timestamp_fields() -> dict:
    """A REAL FreeTSA token for this example's fixed new_raw_html_hash — see
    the module docstring above on why fetching one now isn't backdating.
    tsa_time_utc is read out of the token itself (via the same parser
    production code uses), never hardcoded, so it can't drift out of sync
    with what the embedded token actually says."""
    tsr_bytes = _SAMPLE_TSR_PATH.read_bytes()
    granted, tsa_time = parse_reply(tsr_bytes)
    if not granted:  # pragma: no cover — the checked-in token is known-good
        return {
            "timestamp_status": "failed",
            "tsa_token": None,
            "tsa_authority_url": None,
            "tsa_time_utc": None,
            "tsa_attempt_count": 1,
            "tsa_last_error": "sample token failed to parse",
        }
    return {
        "timestamp_status": "timestamped",
        "tsa_token": tsr_bytes,
        "tsa_authority_url": settings.TSA_PRIMARY_URL,
        "tsa_time_utc": tsa_time,
        "tsa_attempt_count": 1,
        "tsa_last_error": None,
    }
