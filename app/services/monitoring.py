import asyncio
import logging
from collections.abc import Awaitable, Callable
from functools import partial
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.llm.analyzer import LLMDiffAnalyzer
from app.core.scraper.content_health import content_health_issue
from app.core.scraper.detector import ChangeDetector, diff_for_llm
from app.core.scraper.fetcher import fetch_raw_html, mark_subprocessor_requires_browser
from app.core.scraper.hasher import ContentHasher
from app.core.scraper.normalizer import HTMLNormalizer, NORMALIZER_VERSION
from app.db.models.change_event import (
    REVIEW_ACTION_AUTO_PUBLISHED_COSMETIC,
    ChangeEvent,
    ChangeStatus,
    TimestampStatus,
)
from app.db.models.mixins import as_utc, utc_now
from app.db.models.subprocessor import Subprocessor
from app.services.mailer import mailer
from app.services.tier2_budget import try_spend_source_budget, try_spend_tenant_budget

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


# Kept as a module-local name: this file's call sites read better with it.
_naive_to_utc = as_utc


async def _dedupe_and_send(
    subprocessor: Subprocessor,
    session: AsyncSession,
    *,
    stamp_attr: str,
    send: Callable[[str], Awaitable[None]],
) -> None:
    """Shared dedupe-window plumbing for both alarms: send now unless the
    same alarm already fired within MONITORING_ALERT_DEDUPE_DAYS, and — the
    point of a dedupe *window* rather than a one-time latch — resend once
    that window has elapsed and the condition is still true."""
    now = utc_now()
    sent_at = _naive_to_utc(getattr(subprocessor, stamp_attr))
    if sent_at is not None and (now - sent_at) < timedelta(days=settings.MONITORING_ALERT_DEDUPE_DAYS):
        return

    setattr(subprocessor, stamp_attr, now)
    await session.commit()

    recipients = set(settings.admin_email_set)
    if subprocessor.tenant.email:
        recipients.add(subprocessor.tenant.email.lower())
    for email in recipients:
        await send(email)
    logger.info(
        "%s sent for subprocessor %s (%d recipient(s))",
        stamp_attr, subprocessor.id, len(recipients),
    )


async def _record_fetch_failure(subprocessor: Subprocessor, session: AsyncSession, reason: str) -> None:
    """Bumps the resource-health counter and, past the threshold, fires the
    (dedupe-windowed) Monitoring Alert email to the tenant and to admins.
    Independent of the staleness alarm in _check_staleness below — this one
    only ever fires from an actual failed check."""
    subprocessor.consecutive_failure_count += 1
    subprocessor.last_failure_reason = reason
    await session.commit()

    if subprocessor.consecutive_failure_count < settings.MONITORING_ALERT_FAILURE_THRESHOLD:
        return

    await _dedupe_and_send(
        subprocessor,
        session,
        stamp_attr="monitoring_alert_sent_at",
        send=lambda email: mailer.send_monitoring_alert(
            email=email,
            subprocessor_name=subprocessor.name,
            monitored_url=subprocessor.monitored_url,
            consecutive_failures=subprocessor.consecutive_failure_count,
        ),
    )


async def _check_staleness(subprocessor: Subprocessor, session: AsyncSession) -> None:
    """Runs on every tick this subprocessor is examined — including a tick
    that ends up deferred for lack of Tier-2 budget — because it asks a
    single question unrelated to *why* nothing has landed: how long since
    this source was actually, successfully checked. A long budget deferral
    has zero recorded failures and would otherwise be completely invisible."""
    if not subprocessor.is_stale:
        return

    days = (utc_now() - (_naive_to_utc(subprocessor.last_checked_at) or _naive_to_utc(subprocessor.created_at))).days
    await _dedupe_and_send(
        subprocessor,
        session,
        stamp_attr="staleness_alert_sent_at",
        send=lambda email: mailer.send_staleness_alert(
            email=email,
            subprocessor_name=subprocessor.name,
            monitored_url=subprocessor.monitored_url,
            days_since_check=days,
        ),
    )


def _reset_health(subprocessor: Subprocessor) -> None:
    """A successful check clears the failure streak, the staleness clock,
    and both alert dedupe stamps — so a later, unrelated occurrence of
    either alarm fires right away rather than waiting out a stale window."""
    subprocessor.consecutive_failure_count = 0
    subprocessor.last_failure_reason = None
    subprocessor.monitoring_alert_sent_at = None
    subprocessor.staleness_alert_sent_at = None


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

    # c) Staleness alarm — asked on every tick regardless of what happens
    # below, including a tick that ends up deferred: the only question is
    # how long since this source actually, successfully landed a check.
    await _check_staleness(subprocessor, session)

    # d) Tier-2 cost cap — only sources that already require the browser
    # (i.e. run it on *every* check) draw against a budget at all. A source
    # escalating for the first time this run still gets that one attempt; it
    # starts drawing on the budget from the next check onward. Two pools:
    # the source's own quota (the real cost control — see tier2_budget.py)
    # and, past that, the tenant-wide safety valve, sized so normal operation
    # never gets near it. Going over either queues the check — never a
    # silent skip, never a counted failure, this isn't the source's fault —
    # and marks it visibly `tier2_deferred` rather than leaving it looking
    # untouched on the dashboard.
    if subprocessor.requires_browser:
        today = utc_now().date()
        source_ok = await try_spend_source_budget(subprocessor, today, session)
        tenant_ok = True
        if source_ok:
            tenant_ok = await try_spend_tenant_budget(subprocessor.tenant, today, session)
            if not tenant_ok:
                logger.error(
                    "ABNORMAL: tenant %s hit its Tier-2 safety-valve cap (%d/%d) while "
                    "checking subprocessor %s — per-source quotas should never add up to this",
                    subprocessor.tenant_id, subprocessor.tenant.tier2_daily_count,
                    subprocessor.tenant.tier2_daily_limit, subprocessor.id,
                )
                for email in settings.admin_email_set:
                    await mailer.send_tier2_safety_valve_alert(
                        email=email,
                        tenant_name=subprocessor.tenant.name,
                        count=subprocessor.tenant.tier2_daily_count,
                        limit=subprocessor.tenant.tier2_daily_limit,
                    )
        if not source_ok or not tenant_ok:
            logger.info(
                "Tier-2 daily budget exhausted for subprocessor %s — queuing", subprocessor.id,
            )
            subprocessor.next_check_at = utc_now() + _BUDGET_RETRY
            subprocessor.tier2_deferred = True
            await session.commit()
            return

    subprocessor.tier2_deferred = False

    # e) Fetch raw HTML — Tier-1 (httpx) or Tier-2 (Playwright) based on subprocessor state
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
        await _record_fetch_failure(subprocessor, session, "timeout")
        return
    except Exception:
        logger.exception("Failed to fetch %s — retrying in 30 min", subprocessor.monitored_url)
        subprocessor.next_check_at = utc_now() + _FETCH_FAILURE_RETRY
        # Heuristic, not a certainty: fetch_raw_html doesn't surface which
        # tier ultimately raised. A check already pinned to the browser
        # (use_browser=True above) failed there; anything else failed no
        # later than Tier-1's plain HTTP GET.
        reason = "browser_error" if subprocessor.requires_browser else "http_error"
        await _record_fetch_failure(subprocessor, session, reason)
        return

    # f) Normalize, then verify the page is actually content — not a
    # bot-wall interstitial (HTTP 200, looks like "success" to everything
    # above) or an empty/script-only shell. Never store or diff either as a
    # snapshot: a Cloudflare challenge page treated as "no change" would have
    # a tenant believing they're covered for months while nothing is
    # actually being read.
    canonical_text = _normalizer.normalize(raw_html)
    failure_reason = content_health_issue(raw_html, canonical_text)
    if failure_reason is not None:
        logger.warning(
            "Unhealthy content (%s) for %s — treating as fetch failure, retrying in 30 min",
            failure_reason, subprocessor.monitored_url,
        )
        subprocessor.next_check_at = utc_now() + _FETCH_FAILURE_RETRY
        await _record_fetch_failure(subprocessor, session, failure_reason)
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
        subprocessor.content_format_version = NORMALIZER_VERSION
        subprocessor.last_checked_at = now
        subprocessor.next_check_at = next_check
        # This baseline is the only capture of this source that will NEVER
        # become a change_event (nothing existed yet to diff it against) —
        # without this, it would never be timestamp-eligible at all, and
        # it becomes this source's first real change_event's before.html
        # later. Frozen separately from last_raw_html_hash, which keeps
        # moving with every later check.
        subprocessor.baseline_raw_html_hash = new_raw_html_hash
        subprocessor.baseline_timestamp_status = TimestampStatus.pending.value
        _reset_health(subprocessor)
        await session.commit()
        return

    # e2) Our own reading of the page changed, not the page. Re-baseline
    # silently: comparing a hash produced by an older normalizer against
    # one produced by the current one is meaningless, and treating the
    # difference as a change would open a review for every source at once
    # and email every tenant's subscribers about vendor changes that never
    # happened. See migration 0021.
    if subprocessor.content_format_version != NORMALIZER_VERSION:
        logger.info(
            "Normalizer v%d→v%d — re-baselining subprocessor %s without a change event",
            subprocessor.content_format_version,
            NORMALIZER_VERSION,
            subprocessor_id,
        )
        subprocessor.last_content_hash = new_hash
        subprocessor.last_content_text = canonical_text
        subprocessor.last_raw_html = raw_html
        subprocessor.last_raw_html_hash = new_raw_html_hash
        subprocessor.content_format_version = NORMALIZER_VERSION
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

    # g) Analyze diff with LLM before persisting. Trimmed by whole hunks,
    # not by a head-crop: a long page's change is usually near the bottom,
    # and the longest pages belong to the biggest vendors. See
    # detector.diff_for_llm.
    try:
        analysis = await _llm_analyzer.analyze(diff_for_llm(raw_diff))
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
        # Stamped once, here. A tenant who cancels Growth keeps the packs
        # for changes captured while they were paying for them — see
        # migration 0022 and the export routes in dashboard.py.
        export_entitled=subprocessor.tenant.may_export_evidence,
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
        # Explicit, not relied on as the column default: this is a real
        # snapshot just stored, eligible for an RFC 3161 timestamp on the
        # next sweep tick. The column's own default is the terminal
        # not_available_pre_tsa — deliberately the safe state a forgetful
        # caller would fall into, never this one.
        timestamp_status=TimestampStatus.pending.value,
        # No human reviewed a cosmetic auto-publish — reviewed_by_* stays
        # NULL (never a placeholder name like "system"), and review_action
        # records the observed action itself. A material event's
        # review_action is set later, at actual approval time, by
        # app/services/approval.py — never here.
        review_action=REVIEW_ACTION_AUTO_PUBLISHED_COSMETIC if auto_publish else None,
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
