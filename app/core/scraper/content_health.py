"""Shared "is this page actually the content we asked for" check.

Two very different callers need the same keyword list and never should
drift apart: the fetcher (`fetcher.py`) uses it to decide whether Tier-1
must escalate to Tier-2, and the monitoring cycle (`monitoring.py`) uses it
as the final gate before treating a fetch — Tier-1 or Tier-2, whichever
produced it — as a genuine success. A Cloudflare challenge page returns
HTTP 200; without this check it would be diffed and stored as a real
snapshot, silently, forever.
"""

# Markers unique to an interstitial challenge page. Do NOT match on bare
# vendor names: the pages this product monitors are sub-processor lists, so
# almost all of them legitimately contain the word "Cloudflare" — matching
# it flagged every healthy page as bot-walled and pinned it to Tier-2
# forever.
BOT_WALL_KEYWORDS = (
    "just a moment...",
    "checking your browser",
    "cf-browser-verification",
    "__cf_chl",
    "attention required! | cloudflare",
    "enable javascript and cookies to continue",
    "access denied",
    "verify you are human",
    "cf-turnstile",
    "hcaptcha-widget",
)
# Challenge interstitials are tiny; a real policy page is not. Guards against
# a page that merely quotes one of the phrases above.
BOT_WALL_MAX_BODY_CHARS = 20_000


def is_bot_wall_body(body: str) -> bool:
    """Content-based bot-wall detection — no status code involved, so this
    also works on whatever fetch_raw_html hands back regardless of which
    tier produced it."""
    if len(body) > BOT_WALL_MAX_BODY_CHARS:
        return False
    body_lower = body.lower()
    return any(kw in body_lower for kw in BOT_WALL_KEYWORDS)


def content_health_issue(raw_html: str, normalized_text: str) -> str | None:
    """None if the fetched page is healthy content; otherwise a short reason
    code: "bot_wall" (a known challenge/interstitial signature) or
    "empty_content" (below CONTENT_HEALTH_MIN_TEXT_LENGTH of normalized
    visible text — catches an empty body, a script-only render, or any
    interstitial whose wording isn't in BOT_WALL_KEYWORDS)."""
    from app.core.config import settings

    if is_bot_wall_body(raw_html):
        return "bot_wall"
    if len(normalized_text) < settings.CONTENT_HEALTH_MIN_TEXT_LENGTH:
        return "empty_content"
    return None
