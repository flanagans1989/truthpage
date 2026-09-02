"""SSRF guard for any URL this app fetches.

Lifted out of the subprocessors router when the onboarding importer became a
second place that fetches a tenant-supplied URL. One copy, so a fix here
covers both paths rather than half of them.

Two entry points, deliberately different:

- `validate_url` raises HTTPException(422) and belongs in routers, where a
  bad URL is a user error to report.
- `ensure_safe_url` raises `UnsafeUrlError` and belongs in the fetcher and
  the sweep, where a bad URL is an operational failure to record.

Checking a URL once, when it is first submitted, is not enough. Until
2026-09-02 that was the whole guard, which left two holes wide open:

1. Redirects. httpx was configured with follow_redirects=True, so a
   validated, perfectly public URL could 302 straight to 127.0.0.1 or
   169.254.169.254 and the guard never saw the second request. That was
   reachable without an account at all, through the public audit-grader
   tool.
2. Time. A hostname validated at signup is re-fetched every day forever.
   Repointing its DNS at an internal address afterwards was never
   re-checked — a rebinding attack with no time pressure whatsoever.

So the guard now runs on every hop of every fetch, every time. See
app/core/scraper/fetcher.py.

`_validate_monitored_url` resolves DNS, which blocks — call it through
`asyncio.to_thread`, or use one of the async wrappers, which already do.
"""
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import HTTPException

_RESERVED_HOSTNAMES = frozenset({"localhost", "metadata.google.internal"})


def _is_forbidden_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return addr.is_private or addr.is_link_local or addr.is_loopback or addr.is_reserved


def _validate_monitored_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=422, detail="Only http/https URLs are allowed")
    host = parsed.hostname or ""
    if not host:
        raise HTTPException(status_code=422, detail="Invalid URL: missing host")
    if host in _RESERVED_HOSTNAMES:
        raise HTTPException(status_code=422, detail="Reserved hostname not allowed")
    try:
        addr = ipaddress.ip_address(host)
        if _is_forbidden_ip(addr):
            raise HTTPException(status_code=422, detail="Private/reserved IP addresses are not allowed")
        return
    except ValueError:
        pass  # hostname, not a raw IP — resolve it below

    # Resolve the hostname so e.g. 169.254.169.254.nip.io can't reach cloud
    # metadata. Not airtight against DNS rebinding, but blocks the easy path.
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise HTTPException(status_code=422, detail="Hostname could not be resolved")
    for info in infos:
        resolved = ipaddress.ip_address(info[4][0])
        if _is_forbidden_ip(resolved):
            raise HTTPException(status_code=422, detail="Hostname resolves to a private/reserved address")


class UnsafeUrlError(RuntimeError):
    """A URL (or a redirect hop) resolves somewhere we must not fetch."""


async def validate_url(url: str) -> None:
    """Router-facing: raises HTTPException(422). Async because the DNS
    lookup inside must not block the event loop."""
    await asyncio.to_thread(_validate_monitored_url, url)


async def ensure_safe_url(url: str) -> None:
    """Fetcher/sweep-facing: same checks, but raises UnsafeUrlError.

    A fetch path must not raise HTTPException — it is not answering a
    request, and an HTTPException escaping the sweep would be recorded as
    an opaque 4xx instead of the security event it is.
    """
    try:
        await asyncio.to_thread(_validate_monitored_url, url)
    except HTTPException as exc:
        raise UnsafeUrlError(str(exc.detail)) from exc
