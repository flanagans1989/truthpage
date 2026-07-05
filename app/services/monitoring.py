import asyncio
import logging
from datetime import UTC, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.llm.analyzer import LLMDiffAnalyzer
from app.core.scraper.detector import ChangeDetector
from app.core.scraper.fetcher import fetch_raw_html
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

    # c) Fetch raw HTML — Tier-1 (httpx) or Tier-2 (Playwright) based on subprocessor state
    # 90s hard ceiling: 30s page.goto + buffer for browser launch/teardown.
    # Prevents a hung Playwright process from freezing the entire sweep job.
    try:
        raw_html = await asyncio.wait_for(
            fetch_raw_html(
                subprocessor.monitored_url,
                subprocessor_id=subprocessor.id,
                session=session,
                use_browser=subprocessor.requires_browser,
            ),
            timeout=90.0,
        )
    except asyncio.TimeoutError:
        logger.warning("Fetch timed out after 90 s for %s — retrying in 30 min", subprocessor.monitored_url)
        subprocessor.next_check_at = utc_now() + timedelta(minutes=30)
        await session.commit()
        return
    except Exception:
        logger.exception("Failed to fetch %s — retrying in 30 min", subprocessor.monitored_url)
        subprocessor.next_check_at = utc_now() + timedelta(minutes=30)
        await session.commit()
        return

    # d) Normalize and hash
    canonical_text = _normalizer.normalize(raw_html)
    if not canonical_text:
        # Empty body usually means an error page or a broken render, not a
        # genuine policy wipe — never overwrite the baseline with it.
        logger.warning(
            "Empty normalized content for %s — treating as fetch failure, retrying in 30 min",
            subprocessor.monitored_url,
        )
        subprocessor.next_check_at = utc_now() + timedelta(minutes=30)
        await session.commit()
        return
    new_hash = _hasher.hash(canonical_text)

    now = utc_now()
    next_check = now + timedelta(minutes=subprocessor.check_interval_minutes)

    # e) First check — store the baseline silently; there is no "before" to
    # diff against, so a ChangeEvent here would be pure noise.
    if subprocessor.last_content_hash is None:
        logger.info("Baseline captured for subprocessor %s", subprocessor_id)
        subprocessor.last_content_hash = new_hash
        subprocessor.last_content_text = canonical_text
        subprocessor.last_checked_at = now
        subprocessor.next_check_at = next_check
        await session.commit()
        return

    # f) No change — update timestamps only, no LLM cost
    if subprocessor.last_content_hash == new_hash:
        logger.debug("No change detected for subprocessor %s", subprocessor_id)
        subprocessor.last_checked_at = now
        subprocessor.next_check_at = next_check
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
        llm_summary=analysis.summary,
        llm_classification=analysis.classification,
        llm_confidence=analysis.confidence,
        status=status,
    )
    session.add(change_event)

    # h) Update subprocessor state
    subprocessor.last_content_hash = new_hash
    subprocessor.last_content_text = canonical_text
    subprocessor.last_checked_at = now
    subprocessor.next_check_at = next_check

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
