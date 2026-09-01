"""Monitoring for the public vendor directory.

The tenant pipeline and this one share the scraper, the hasher and the
differ, but not their endings. A tenant's change waits in a queue for a
human and then emails subscribers; a directory change publishes itself and
re-extracts the list, because nobody's obligations hang on it and a
directory that waits for a reviewer is a directory that is wrong.
"""
import asyncio
import logging
from datetime import timedelta
from functools import partial
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.analyzer import LLMDiffAnalyzer
from app.core.llm.extractor import SubProcessorExtractor, diff_entries
from app.core.scraper.detector import ChangeDetector
from app.core.scraper.fetcher import fetch_raw_html
from app.core.scraper.hasher import ContentHasher
from app.core.scraper.normalizer import HTMLNormalizer
from app.db.models.mixins import utc_now
from app.db.models.vendor import Vendor, VendorChange

logger = logging.getLogger(__name__)

_normalizer = HTMLNormalizer()
_hasher = ContentHasher()
_detector = ChangeDetector()
_analyzer = LLMDiffAnalyzer()
_extractor = SubProcessorExtractor()

_FETCH_TIMEOUT = 90.0
_RETRY_AFTER = timedelta(minutes=30)


async def _mark_vendor_requires_browser(vendor_id: UUID, session: AsyncSession) -> None:
    await session.execute(
        update(Vendor).where(Vendor.id == vendor_id).values(requires_browser=True)
    )
    await session.commit()


async def _refresh_entries(vendor: Vendor, page_text: str) -> list[dict] | None:
    """Re-extract the list. Returns None when extraction fails.

    A failure must leave the previous list in place: a vendor page showing
    nothing is worse than one showing last week's entries, and the next check
    will try again.
    """
    try:
        extracted = await _extractor.extract(page_text)
    except Exception:
        logger.exception("Extraction failed for vendor %s", vendor.slug)
        return None
    rows = [e.model_dump() for e in extracted.entries]
    if not rows:
        logger.warning("Extraction returned no entries for vendor %s", vendor.slug)
        return None
    return rows


async def run_vendor_check(vendor_id: UUID, session: AsyncSession) -> None:
    """One directory page: fetch → hash → diff → classify → re-extract."""
    vendor = (
        await session.execute(select(Vendor).where(Vendor.id == vendor_id))
    ).scalar_one_or_none()
    if vendor is None:
        logger.warning("Vendor %s not found", vendor_id)
        return

    try:
        raw_html = await asyncio.wait_for(
            fetch_raw_html(
                vendor.monitored_url,
                use_browser=vendor.requires_browser,
                on_escalate=partial(_mark_vendor_requires_browser, vendor.id, session),
            ),
            timeout=_FETCH_TIMEOUT,
        )
    except Exception:
        logger.exception("Vendor fetch failed for %s — retrying later", vendor.monitored_url)
        vendor.next_check_at = utc_now() + _RETRY_AFTER
        await session.commit()
        return

    canonical_text = _normalizer.normalize(raw_html)
    if not canonical_text:
        logger.warning("Empty content for vendor %s — treating as a fetch failure", vendor.slug)
        vendor.next_check_at = utc_now() + _RETRY_AFTER
        await session.commit()
        return

    new_hash = _hasher.hash(canonical_text)
    now = utc_now()
    next_check = now + timedelta(minutes=vendor.check_interval_minutes)

    # First sighting: extract, and publish only if there is something to show.
    if vendor.last_content_hash is None:
        rows = await _refresh_entries(vendor, canonical_text)
        vendor.last_content_hash = new_hash
        vendor.last_content_text = canonical_text
        vendor.last_checked_at = now
        vendor.next_check_at = next_check
        if rows is not None:
            vendor.entries = rows
            vendor.entries_updated_at = now
            vendor.is_published = True
            logger.info("Vendor %s published with %d entries", vendor.slug, len(rows))
        else:
            logger.info("Vendor %s baselined but not published — no list found", vendor.slug)
        await session.commit()
        return

    if vendor.last_content_hash == new_hash:
        vendor.last_checked_at = now
        vendor.next_check_at = next_check
        await session.commit()
        return

    raw_diff = _detector.unified_diff(
        old_text=vendor.last_content_text or "",
        new_text=canonical_text,
        label=vendor.monitored_url,
    )
    analysis = await _analyzer.analyze(raw_diff[:12_000])
    rows = await _refresh_entries(vendor, canonical_text)
    added, removed = diff_entries(vendor.entries, rows) if rows is not None else ([], [])

    session.add(
        VendorChange(
            vendor_id=vendor.id,
            old_hash=vendor.last_content_hash or "",
            new_hash=new_hash,
            raw_diff=raw_diff,
            summary=analysis.summary,
            classification=analysis.classification,
            confidence=analysis.confidence,
            added=added,
            removed=removed,
        )
    )

    vendor.last_content_hash = new_hash
    vendor.last_content_text = canonical_text
    vendor.last_checked_at = now
    vendor.next_check_at = next_check
    if rows is not None:
        vendor.entries = rows
        vendor.entries_updated_at = now
        vendor.is_published = True

    await session.commit()
    logger.info(
        "Vendor %s changed: %s (+%d/-%d entries)",
        vendor.slug, analysis.classification, len(added), len(removed),
    )


async def sweep_due_vendors(session_factory) -> None:
    """Directory pages whose check window has elapsed.

    Runs in the same tick as the tenant sweep. The compute cost is the scrape
    itself, not a database wake-up: the connection is already open for the
    tenant pass, so adding directory pages does not add Neon compute hours —
    the thing that took the site down in August was the tick frequency, not
    the number of pages.
    """
    now = utc_now()
    async with session_factory() as session:
        due = list(
            (
                await session.execute(
                    select(Vendor).where(
                        (Vendor.next_check_at <= now) | (Vendor.next_check_at == None)  # noqa: E711
                    )
                )
            ).scalars().all()
        )

    if not due:
        return

    logger.info("Directory sweep: %d vendor page(s) due", len(due))
    for vendor in due:
        async with session_factory() as session:
            try:
                await run_vendor_check(vendor.id, session)
            except Exception:
                logger.exception("Directory sweep: unhandled error for vendor %s", vendor.slug)
