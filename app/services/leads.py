"""Lead capture for the public growth tools, and the fictional example
event behind the sample evidence ZIP.

See app.db.models.lead.Lead for why a lead is its own table rather than a
passwordless Tenant.
"""
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.lead import Lead


async def record_lead(
    *, email: str, source: str, context: str | None, session: AsyncSession
) -> None:
    lead = Lead(email=email.strip().lower(), source=source, context=context)
    session.add(lead)
    await session.commit()


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
        old_hash="a3f5c9e1d7b2f4a6c8e0b1d3f5a7c9e1d3b5f7a9c1e3d5b7f9a1c3e5d7b9f1a3",
        new_hash="c9e1d3f5a7b9c1e3d5f7a9b1c3e5d7f9a1b3c5e7d9f1a3b5c7e9d1f3a5b7c9e1",
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
        old_raw_html_hash="7d9f1a3c5e7b9d1f3a5c7e9b1d3f5a7c9e1b3d5f7a9c1e3b5d7f9a1c3e5b7d9",
        new_raw_html_hash="1f3a5c7e9b1d3f5a7c9e1b3d5f7a9c1e3b5d7f9a1c3e5b7d9f1a3c5e7b9d1f3",
        raw_diff=(
            "--- before\n+++ after\n"
            "@@ -1 +1 @@\n"
            "-Sub-processors: AWS (hosting, United States), Cloudflare (CDN, United States).\n"
            "+Sub-processors: AWS (hosting, United States), Cloudflare (CDN, United States), "
            "Example Cloud Services Inc. (payment fraud analysis, United States).\n"
        ),
    )
