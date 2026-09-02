import asyncio
import logging
from functools import partial
from datetime import UTC, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.llm.analyzer import LLMDiffAnalyzer
from app.core.scraper.detector import ChangeDetector
from app.core.scraper.fetcher import fetch_raw_html, mark_subprocessor_requires_browser
from app.core.scraper.hasher import ContentHasher
from app.core.scraper.normalizer import HTMLNormalizer
from app.db.models.change_event import ChangeEvent, ChangeStatus
from app.db.models.mixins import utc_now
from app.db.models.subprocessor import Subprocessor
from app.services.mailer import mailer

logger = logging.getLogger(__name__)

_normalizer = HTMLNormalizer()
_hasher = ContentHasher()
_detector = ChangeDetector()
_llm_analyzer = LLMDiffAnalyzer()

_AUTO_PUBLISH_CLASSIFICATION = "COSMETIC"
_AUTO_PUBLISH_CONFIDENCE_THRESHOLD = 0.85

# How long a Tier-2 run deferred by the daily budget waits before retrying —
# short enough that a source queued early in the day still gets its regular
# check_interval_minutes cadence once the next UTC day's budget opens up.
_BUDGET_RETRY = timedelta(hours=1)
_FETCH_FAILURE_RETRY = timedelta(minutes=30)


async def _record_fetch_failure(subprocessor: Subprocessor, session: AsyncSession) -> None:
    """Bumps the resource-health counter and, past the threshold, fires the
    (dedupe-windowed) Monitoring Alert email to the tenant and to admins."""
    subprocessor.consecutive_failure_count += 1
    await session.commit()

    if subprocessor.consecutive_failure_count < settings.MONITORING_ALERT_FAILURE_THRESHOLD:
        return

    now = utc_now()
    if subprocessor.monitoring_alert_sent_at is not None:
        sent_at = subprocessor.monitoring_alert_sent_at
        if sent_at.tzinfo is None:
            # SQLite (tests only — Postgres round-trips tz-aware values)
            # hands back a naive datetime; we only ever write UTC into this
            # column, so that's the correct zone to attach.
            sent_at = sent_at.replace(tzinfo=UTC)
        dedupe_elapsed = now - sent_at
        if dedupe_elapsed < timedelta(days=settings.MONITORING_ALERT_DEDUPE_DAYS):
            return

    subprocessor.monitoring_alert_sent_at = now
    await session.commit()

    recipients = set(settings.admin_email_set)
    if subprocessor.tenant.email:
        recipients.add(subprocessor.tenant.email.lower())
    for email in recipients:
        await mailer.send_monitoring_alert(
            email=email,
            subprocessor_name=subprocessor.name,
            monitored_url=subprocessor.monitored_url,
            consecutive_failures=subprocessor.consecutive_failure_count,
        )
    logger.info(
        "Monitoring alert sent for subprocessor %s (%d recipient(s), %d consecutive failures)",
        subprocessor.id, len(recipients), subprocessor.consecutive_failure_count,
    )


def _reset_health(subprocessor: Subprocessor) -> None:
    """A successful check clears the failure streak — and the alert dedupe
    stamp with it, so a later, unrelated streak alerts right away."""
    subprocessor.consecutive_failure_count = 0
    subprocessor.monitoring_alert_sent_at = None


async def run_subprocessor_check(subprocessor_id: UUID, session: AsyncSession) -> None:
    """
    Orchestrates a single subprocessor monitoring cycle:
    fetch → normalize → hash → diff → LLM analysis → persist.
    """
    # a) Load subprocessor with tenant (explicit join to avoid lazy-raise)
    result = await session.execute(
        select(Subprocessor)
        .where(Subprocessor.id == subprocessor_id)
        .options(selectinload(Subprocessor.tenant))
    )
    subprocessor: Subprocessor | None = result.scalar_one_or_none()

    # b) Guard: missing or disabled
    if subprocessor is None:
        logger.warning("Subprocessor %s not found", subprocessor_id)
        return
    if not subprocessor.monitoring_enabled:
        logger.debug("Subprocessor %s monitoring disabled, skipping", subprocessor_id)
        return

    # c) Tier-2 cost cap — only sources that already require the browser
    # (i.e. run it on *every* check) draw against the tenant's daily budget.
    # A source escalating for the first time this run still gets that one
    # attempt; it starts drawing on the budget from the next check onward.
    # Going over the budget queues the check (never a silent skip, never a
    # counted failure — this isn't the source's fault).
    if subprocessor.requires_browser:
        if not subprocessor.tenant.consume_tier2_budget(utc_now().date()):
            logger.info(
                "Tier-2 daily budget exhausted for tenant %s — queuing subprocessor %s",
                subprocessor.tenant_id, subprocessor.id,
            )
            subprocessor.next_check_at = utc_now() + _BUDGET_RETRY
            await session.commit()
            return
        await session.commit()

    # d) Fetch raw HTML — Tier-1 (httpx) or Tier-2 (Playwright) based on subprocessor state
    # 90s hard ceiling: 30s page.goto + buffer for browser launch/teardown.
    # Prevents a hung Playwright process from freezing the entire sweep job.
    try:
        raw_html = await asyncio.wait_for(
            fetch_raw_html(
                subprocessor.monitored_url,
                use_browser=subprocessor.requires_browser,
                on_escalate=partial(
                    mark_subprocessor_requires_browser, subprocessor.id, session
                ),
            ),
            timeout=90.0,
        )
    except asyncio.TimeoutError:
        logger.warning("Fetch timed out after 90 s for %s — retrying in 30 min", subprocessor.monitored_url)
        subprocessor.next_check_at = utc_now() + _FETCH_FAILURE_RETRY
        await _record_fetch_failure(subprocessor, session)
        return
    except Exception:
        logger.exception("Failed to fetch %s — retrying in 30 min", subprocessor.monitored_url)
        subprocessor.next_check_at = utc_now() + _FETCH_FAILURE_RETRY
        await _record_fetch_failure(subprocessor, session)
        return

    # e) Normalize and hash
    canonical_text = _normalizer.normalize(raw_html)
    if not canonical_text:
        # Empty body usually means an error page or a broken render, not a
        # genuine policy wipe — never overwrite the baseline with it.
        logger.warning(
            "Empty normalized content for %s — treating as fetch failure, retrying in 30 min",
            subprocessor.monitored_url,
        )
        subprocessor.next_check_at = utc_now() + _FETCH_FAILURE_RETRY
        await _record_fetch_failure(subprocessor, session)
        return
    new_hash = _hasher.hash(canonical_text)
    # Digest of the document itself, for the evidence bundle — distinct from
    # new_hash above, which is over the normalized text change detection
    # compares. A tenant re-hashing the downloaded after.html must get this
    # value, not the normalized one.
    new_raw_html_hash = _hasher.hash(raw_html)

    now = utc_now()
    next_check = now + timedelta(minutes=subprocessor.check_interval_minutes)

    # e) First check — store the baseline silently; there is no "before" to
    # diff against, so a ChangeEvent here would be pure noise.
    if subprocessor.last_content_hash is None:
        logger.info("Baseline captured for subprocessor %s", subprocessor_id)
        subprocessor.last_content_hash = new_hash
        subprocessor.last_content_text = canonical_text
        subprocessor.last_raw_html = raw_html
        subprocessor.last_raw_html_hash = new_raw_html_hash
        subprocessor.last_checked_at = now
        subprocessor.next_check_at = next_check
        _reset_health(subprocessor)
        await session.commit()
        return

    # f) No change — update timestamps only, no LLM cost
    if subprocessor.last_content_hash == new_hash:
        logger.debug("No change detected for subprocessor %s", subprocessor_id)
        subprocessor.last_checked_at = now
        subprocessor.next_check_at = next_check
        _reset_health(subprocessor)
        await session.commit()
        return

    # f) Change detected — produce diff
    raw_diff = _detector.unified_diff(
        old_text=subprocessor.last_content_text or "",
        new_text=canonical_text,
        label=subprocessor.monitored_url,
    )
    logger.info("Change detected for subprocessor %s", subprocessor_id)

    # g) Analyze diff with LLM before persisting (truncate to ~12k chars ≈ ~3k tokens)
    diff_for_llm = raw_diff[:12_000] if len(raw_diff) > 12_000 else raw_diff
    try:
        analysis = await _llm_analyzer.analyze(diff_for_llm)
        logger.info(
            "LLM analysis for subprocessor %s: %s (confidence=%.2f)",
            subprocessor_id,
            analysis.classification,
            analysis.confidence,
        )
    except Exception:
        logger.exception("LLM analysis failed for subprocessor %s, defaulting to UNCERTAIN", subprocessor_id)
        from app.core.llm.schemas import DiffAnalysis
        analysis = DiffAnalysis(
            summary="LLM analysis failed — manual review required.",
            classification="UNCERTAIN",
            confidence=0.0,
        )

    auto_publish = (
        analysis.classification == _AUTO_PUBLISH_CLASSIFICATION
        and analysis.confidence > _AUTO_PUBLISH_CONFIDENCE_THRESHOLD
    )
    status = ChangeStatus.auto_published.value if auto_publish else ChangeStatus.pending_review.value

    change_event = ChangeEvent(
        subprocessor_id=subprocessor.id,
        old_hash=subprocessor.last_content_hash or "",
        new_hash=new_hash,
        raw_diff=raw_diff,
        old_content_text=subprocessor.last_content_text,
        new_content_text=canonical_text,
        old_raw_html=subprocessor.last_raw_html,
        new_raw_html=raw_html,
        old_raw_html_hash=subprocessor.last_raw_html_hash,
        new_raw_html_hash=new_raw_html_hash,
        llm_summary=analysis.summary,
        llm_classification=analysis.classification,
        llm_confidence=analysis.confidence,
        status=status,
    )
    session.add(change_event)

    # h) Update subprocessor state
    subprocessor.last_content_hash = new_hash
    subprocessor.last_content_text = canonical_text
    subprocessor.last_raw_html = raw_html
    subprocessor.last_raw_html_hash = new_raw_html_hash
    subprocessor.last_checked_at = now
    subprocessor.next_check_at = next_check
    _reset_health(subprocessor)

    await session.commit()

    # i) Alert the tenant owner — pending changes are invisible until someone
    # opens the dashboard, so email is the only push signal they get.
    if not auto_publish and subprocessor.tenant.email:
        await mailer.send_review_needed(
            email=subprocessor.tenant.email,
            subprocessor_name=subprocessor.name,
            monitored_url=subprocessor.monitored_url,
            summary=analysis.summary,
            classification=analysis.classification,
        )
