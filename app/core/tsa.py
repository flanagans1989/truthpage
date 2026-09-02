"""RFC 3161 timestamping client.

Shells out to the system `openssl` binary — already a hard requirement for
`verify.sh` in every evidence ZIP (openssl only, no network) — rather than
hand-rolling ASN.1 DER encoding/parsing for the request and reply. One
implementation of "build a TS query" and "read a TS reply", not two that
could quietly disagree about what's valid.

Only ever sends a SHA-256 digest to the TSA, never page content — the TSA
never sees what a tenant is monitoring. See docs/manifest_v2.md and the
evidence ZIP's README.txt, which say the same thing to the auditor.
"""
import asyncio
import logging
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_STATUS_GRANTED_RE = re.compile(r"Status:\s*Granted\.")
_TIME_STAMP_RE = re.compile(r"^Time stamp:\s*(.+)$", re.MULTILINE)

_OPENSSL_TIMEOUT_SECONDS = 15


class TSAError(RuntimeError):
    """A timestamp request failed, or the TSA's reply could not be read as
    a granted RFC 3161 token."""


def _run_openssl(args: list[str], input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["openssl", *args],
        input=input_bytes,
        capture_output=True,
        timeout=_OPENSSL_TIMEOUT_SECONDS,
    )


def build_query(digest_hex: str) -> bytes:
    """A TS query for an already-computed SHA-256 hex digest.

    `-cert` asks the TSA to embed its own signing certificate in the reply
    — the only way an offline verify.sh can chain-verify with nothing but
    the bundled root CA and no network fetch for the signer cert.

    No nonce (`-no_nonce`): the reply is checked against the same digest
    either way, so replaying a genuine response for a query it actually
    answered carries no forgery risk, and skipping it means verify.sh
    doesn't need to track/match one either.
    """
    result = _run_openssl(["ts", "-query", "-digest", digest_hex, "-sha256", "-cert", "-no_nonce"])
    if result.returncode != 0:
        raise TSAError(f"openssl ts -query failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def parse_reply(tsr_bytes: bytes) -> tuple[bool, datetime | None]:
    """Reads a .tsr reply enough to record what the TSA claimed: whether it
    was granted, and the time it reports. This does NOT verify the
    signature chain — that's /verify's and verify.sh's job, against the
    bundled CA. A record here reflects the request having succeeded, not
    having been independently checked."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "reply.tsr"
        path.write_bytes(tsr_bytes)
        result = _run_openssl(["ts", "-reply", "-in", str(path), "-text"])

    output = result.stdout.decode(errors="replace")
    if result.returncode != 0 or not _STATUS_GRANTED_RE.search(output):
        return False, None

    match = _TIME_STAMP_RE.search(output)
    if not match:
        return True, None
    # openssl pads a single-digit day with an extra space ("Sep  2 ...");
    # collapsing whitespace before parsing handles that without a special case.
    raw = " ".join(match.group(1).split())
    raw = raw.removesuffix(" GMT")
    try:
        parsed = datetime.strptime(raw, "%b %d %H:%M:%S %Y").replace(tzinfo=UTC)
    except ValueError:
        logger.warning("Could not parse TSA reply timestamp: %r", raw)
        return True, None
    return True, parsed


async def request_timestamp(
    digest_hex: str, tsa_url: str, timeout_seconds: float
) -> tuple[bytes, datetime | None]:
    """Sends ONLY `digest_hex` to `tsa_url` — never file content. Returns
    the raw .tsr token bytes and the time the TSA reported having granted
    it. Raises TSAError on any failure (network, non-200, malformed or
    non-granted reply); the caller decides retry/backoff policy."""
    query = await asyncio.to_thread(build_query, digest_hex)

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                tsa_url,
                content=query,
                headers={"Content-Type": "application/timestamp-query"},
            )
    except httpx.HTTPError as exc:
        raise TSAError(f"request to {tsa_url} failed: {exc}") from exc

    if response.status_code != 200:
        raise TSAError(f"{tsa_url} returned HTTP {response.status_code}")

    tsr_bytes = response.content
    granted, tsa_time = await asyncio.to_thread(parse_reply, tsr_bytes)
    if not granted:
        raise TSAError(f"{tsa_url} did not grant the timestamp request")
    return tsr_bytes, tsa_time
