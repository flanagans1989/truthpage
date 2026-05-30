import logging
import random
from uuid import UUID

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.subprocessor import Subprocessor

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
]

_BOT_WALL_STATUS_CODES = frozenset([403, 429, 503])
_BOT_WALL_KEYWORDS = ("cloudflare", "just a moment", "ddos", "access denied", "please wait")

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _random_headers() -> dict[str, str]:
    return {
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def _is_bot_protected(status_code: int, body: str) -> bool:
    if status_code in _BOT_WALL_STATUS_CODES:
        return True
    body_lower = body.lower()
    return any(kw in body_lower for kw in _BOT_WALL_KEYWORDS)


async def _fetch_tier1(url: str) -> tuple[str, bool]:
    """Returns (html, bot_blocked). Uses httpx with HTTP/2 and UA rotation."""
    async with httpx.AsyncClient(
        headers=_random_headers(),
        timeout=_TIMEOUT,
        follow_redirects=True,
        http2=True,
    ) as client:
        response = await client.get(url)
        html = response.text
        blocked = _is_bot_protected(response.status_code, html)
        return html, blocked


async def _fetch_tier2(url: str) -> str:
    """Playwright headless Chromium fallback. Waits for network to settle."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=60_000)
            html = await page.content()
        finally:
            await browser.close()

    return html


async def _mark_requires_browser(subprocessor_id: UUID, session: AsyncSession) -> None:
    """Caches the fact that this URL needs Playwright so future checks skip Tier-1."""
    await session.execute(
        update(Subprocessor)
        .where(Subprocessor.id == subprocessor_id)
        .values(requires_browser=True)
    )
    await session.commit()


async def fetch_raw_html(
    url: str,
    *,
    subprocessor_id: UUID,
    session: AsyncSession,
    use_browser: bool = False,
) -> str:
    """
    Multi-tier fetcher:
      Tier-1 — httpx + HTTP/2 + UA rotation (fast, cheap)
      Tier-2 — Playwright headless Chromium (heavy, bot-proof)

    If Tier-1 is bot-blocked, escalates to Tier-2 and persists
    requires_browser=True so the next cycle skips Tier-1 entirely.
    """
    if not use_browser:
        html, blocked = await _fetch_tier1(url)
        if not blocked:
            return html
        logger.info("Bot protection detected for %s — escalating to Tier-2 (Playwright)", url)

    html = await _fetch_tier2(url)

    if not use_browser:
        # Tier-1 was blocked; cache result so next run goes directly to Tier-2
        await _mark_requires_browser(subprocessor_id, session)

    return html
