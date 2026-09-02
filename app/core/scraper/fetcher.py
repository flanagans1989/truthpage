import logging
import random
from collections.abc import Awaitable, Callable
from uuid import UUID

import httpx
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scraper.content_health import is_bot_wall_body
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
    return is_bot_wall_body(body)


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
        if not blocked and response.status_code >= 400:
            # Error page (404/500/…) — never treat its HTML as page content,
            # or the error page would be diffed against the real policy.
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code} for {url}",
                request=response.request,
                response=response,
            )
        return html, blocked


async def _fetch_tier2(url: str) -> str:
    """Playwright headless Chromium fallback. Waits for network to settle."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            if response is not None and response.status >= 400:
                raise RuntimeError(f"HTTP {response.status} for {url} (Tier-2)")
            html = await page.content()
        finally:
            await browser.close()

    return html


async def mark_subprocessor_requires_browser(
    subprocessor_id: UUID, session: AsyncSession
) -> None:
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
    use_browser: bool = False,
    on_escalate: Callable[[], Awaitable[None]] | None = None,
) -> str:
    """
    Multi-tier fetcher:
      Tier-1 — httpx + HTTP/2 + UA rotation (fast, cheap)
      Tier-2 — Playwright headless Chromium (heavy, bot-proof)

    If Tier-1 is bot-blocked, escalates to Tier-2 and calls `on_escalate` so
    the caller can persist that fact — the fetcher does not know whether the
    URL belongs to a tenant's subprocessor or to a directory vendor.
    """
    if not use_browser:
        try:
            html, blocked = await _fetch_tier1(url)
        except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            logger.info("Tier-1 connection error for %s (%s) — escalating to Tier-2", url, exc)
            blocked = True
            html = ""
        if not blocked:
            return html
        if not html:
            logger.info("Bot protection or connection failure for %s — escalating to Tier-2 (Playwright)", url)
        else:
            logger.info("Bot protection detected for %s — escalating to Tier-2 (Playwright)", url)

    html = await _fetch_tier2(url)

    if not use_browser and on_escalate is not None:
        # Tier-1 was blocked; let the caller record it against whatever table
        # owns this URL, so the next run goes straight to Tier-2.
        await on_escalate()

    return html


class BotWallError(RuntimeError):
    """Tier-1 was blocked and the caller cannot afford Tier-2."""


async def fetch_html_fast(url: str) -> str:
    """Tier-1 only, for requests a human is waiting on.

    The onboarding importer runs inside a page load, and Playwright takes
    twenty to thirty seconds on a cold container — long enough that the
    tenant assumes it broke. Raising here is the better outcome: the importer
    can tell them to paste the text, which they can do faster than we could
    have escalated.
    """
    html, blocked = await _fetch_tier1(url)
    if blocked:
        raise BotWallError(f"Tier-1 blocked for {url}")
    return html
