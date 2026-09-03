"""robots.txt compliance for pages we crawl on our own initiative.

Scope is deliberate. Two different pipelines fetch pages here, and they
stand in very different relationships to the site being read:

- A TENANT's monitored URL is fetched because a customer asserted, under
  the Terms, that they may monitor that page — usually their own vendor's
  page, often one they are contractually entitled to watch. We do not
  substitute our judgment for theirs, and silently refusing to monitor a
  page someone is paying to have monitored would be the same class of
  silent failure this codebase has spent the last several fixes closing.

- The public VENDOR DIRECTORY is fetched on nobody's instruction but ours.
  There is no customer relationship, no contract, and the exposure — legal
  and reputational — is entirely ours. A company selling compliance while
  ignoring the one machine-readable "please don't" the web has is not a
  defensible position, and it is the exact criticism a competitor would
  reach for first.

So the directory honours robots.txt and the tenant pipeline does not. See
app/services/directory.py.

Failure handling is allow-on-error rather than the conservative reading of
RFC 9309 §2.3.1.4. A robots.txt that 5xxs or times out for a minute would
otherwise stop monitoring a vendor page with no error anywhere — and this
codebase's recurring bug has been exactly that: correctness handled by
quietly doing nothing. Once a day per page, allow-on-error is the smaller
risk, and it is logged.
"""
import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# One robots.txt fetch per host per six hours. Pages here are checked daily,
# so this costs at most one extra request per host per day.
_CACHE: TTLCache = TTLCache(maxsize=512, ttl=6 * 60 * 60)

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# What we call ourselves when asking permission. Matching on this means a
# site owner can allow or refuse TrustPages specifically, which is the
# whole point of asking.
ROBOTS_USER_AGENT = "TrustPagesBot"


async def _load(origin: str) -> RobotFileParser | None:
    parser = RobotFileParser()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(
                f"{origin}/robots.txt",
                headers={"User-Agent": f"{ROBOTS_USER_AGENT}/1.0 (+https://usetrustpages.com/bot)"},
            )
    except Exception as exc:
        logger.info("robots.txt unreachable for %s (%s) — allowing", origin, exc)
        return None

    if response.status_code >= 500:
        logger.info("robots.txt returned %d for %s — allowing", response.status_code, origin)
        return None
    if response.status_code >= 400:
        # No robots.txt is an explicit "everything is allowed" under RFC 9309.
        parser.parse([])
        return parser

    parser.parse(response.text.splitlines())
    return parser


async def is_allowed(url: str) -> bool:
    """True when robots.txt permits us to fetch this URL (or says nothing)."""
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return True
    origin = f"{parsed.scheme}://{parsed.netloc}"

    if origin in _CACHE:
        parser = _CACHE[origin]
    else:
        parser = await _load(origin)
        _CACHE[origin] = parser

    if parser is None:
        return True
    return parser.can_fetch(ROBOTS_USER_AGENT, url)
