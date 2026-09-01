"""SSRF guard for any URL a tenant hands us to fetch.

Lifted out of the subprocessors router when the onboarding importer became a
second place that fetches a tenant-supplied URL. One copy, so a fix here
covers both paths rather than half of them.

`_validate_monitored_url` resolves DNS, which blocks — call it through
`asyncio.to_thread`, or use `validate_url` which already does.
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


async def validate_url(url: str) -> None:
    """Async wrapper — the DNS lookup inside must not block the event loop."""
    await asyncio.to_thread(_validate_monitored_url, url)
