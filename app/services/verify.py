"""Public, unauthenticated verification of a TrustPages audit evidence pack
— either the whole .zip, or a content file + its .tsr token.

Hard rules, non-negotiable:
  - Never touches the database. Nothing here imports a session, a model,
    or a router that could reach one. This checks a file against math and
    a CA certificate, nothing else — a name/vendor/tenant lookup by hash
    would let anyone probe "does X monitor Y", which is a data leak.
  - Never trusts a CA chain found INSIDE the upload. A zip's own
    tsa-chain.pem (or an uploaded chain in the file+token mode) is not
    read for trust purposes at all — verification is only ever against
    _BUNDLED_CHAINS, checked into this repo. Otherwise anyone could bundle
    their own throwaway CA next to a self-signed "token" and have it
    "verify".
  - Nothing uploaded is written to permanent disk or logged. Token bytes
    that must reach `openssl` on the filesystem go into a
    tempfile.TemporaryDirectory(), deleted before the request returns.
"""
import hashlib
import re
import tempfile
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from app.services.evidence import detect_manifest_version, parse_manifest_v2

_BUNDLED_CHAINS = [
    Path(__file__).parent.parent / "static_data" / "tsa" / "freetsa-chain.pem",
]

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_ZIP_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB total, across all entries
MAX_ZIP_ENTRIES = 100
MAX_SINGLE_ENTRY_BYTES = 20 * 1024 * 1024  # 20 MB, guards a single oversized entry

_V1_ANCHOR_HASH_RE = re.compile(r"Content Hash \(SHA-256\):\s*([0-9a-f]{64})")


@dataclass
class VerifyResult:
    ok: bool
    message: str
    manifest_version: int | None = None
    content_hash: str | None = None
    timestamp_status: str | None = None
    tsa_authority_url: str | None = None
    tsa_time_utc: str | None = None


def _run_openssl_verify(token_bytes: bytes, digest_hex: str) -> bool:
    """True iff `token_bytes` is a valid RFC 3161 token over `digest_hex`,
    chaining to one of _BUNDLED_CHAINS — never a chain from the upload."""
    import subprocess

    with tempfile.TemporaryDirectory() as tmp:
        token_path = Path(tmp) / "token.tsr"
        token_path.write_bytes(token_bytes)
        for chain_path in _BUNDLED_CHAINS:
            result = subprocess.run(
                ["openssl", "ts", "-verify", "-in", str(token_path),
                 "-digest", digest_hex, "-CAfile", str(chain_path)],
                capture_output=True,
                timeout=15,
            )
            if result.returncode == 0:
                return True
    return False


def _zip_bomb_guard(zf: zipfile.ZipFile) -> str | None:
    """None if the archive is safe to read; else a message explaining why
    it was refused. Checked BEFORE any entry is decompressed."""
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        return f"archive has too many files ({len(infos)} > {MAX_ZIP_ENTRIES})"
    total = 0
    for info in infos:
        if info.file_size > MAX_SINGLE_ENTRY_BYTES:
            return f"a single file in the archive is too large ({info.filename})"
        total += info.file_size
        if total > MAX_ZIP_UNCOMPRESSED_BYTES:
            return "archive is too large uncompressed"
    return None


def verify_pack(zip_bytes: bytes) -> VerifyResult:
    if len(zip_bytes) > MAX_UPLOAD_BYTES:
        return VerifyResult(ok=False, message=f"file too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")

    try:
        zf = zipfile.ZipFile(BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return VerifyResult(ok=False, message="not a valid ZIP file")

    guard_message = _zip_bomb_guard(zf)
    if guard_message:
        return VerifyResult(ok=False, message=f"refused: {guard_message}")

    names = set(zf.namelist())
    if "manifest.txt" not in names:
        return VerifyResult(ok=False, message="no manifest.txt found in the archive")

    manifest_text = zf.read("manifest.txt").decode("utf-8", errors="replace")
    version = detect_manifest_version(manifest_text)

    if version == 1:
        return _verify_v1(zf, names, manifest_text)
    return _verify_v2(zf, names, manifest_text)


def _hash_and_check(zf: zipfile.ZipFile, filename: str, expected_hash: str) -> tuple[bool, str]:
    if filename not in zf.namelist():
        return False, f"manifest names {filename!r} but it is not in the archive"
    content = zf.read(filename)
    actual = hashlib.sha256(content).hexdigest()
    if actual != expected_hash:
        return False, f"content hash mismatch: {filename} does not match manifest.txt"
    return True, actual


def _verify_v1(zf: zipfile.ZipFile, names: set[str], manifest_text: str) -> VerifyResult:
    match = _V1_ANCHOR_HASH_RE.search(manifest_text)
    if not match:
        return VerifyResult(ok=False, message="v1 pack has no recoverable content hash", manifest_version=1)
    expected_hash = match.group(1)
    ok, detail = _hash_and_check(zf, "after.html", expected_hash)
    if not ok:
        return VerifyResult(ok=False, message=detail, manifest_version=1)
    return VerifyResult(
        ok=True,
        message="NO TIMESTAMP — this pack predates independent timestamping; content hash matches",
        manifest_version=1,
        content_hash=expected_hash,
        timestamp_status="not_available_pre_tsa",
    )


def _verify_v2(zf: zipfile.ZipFile, names: set[str], manifest_text: str) -> VerifyResult:
    fields = parse_manifest_v2(manifest_text)
    after_file = fields.get("after_html_file")
    expected_hash = fields.get("after_sha256")
    status = fields.get("timestamp_status")

    if not after_file or not expected_hash or expected_hash == "not_available":
        return VerifyResult(ok=False, message="manifest.txt has no content hash to verify against", manifest_version=2)

    ok, detail = _hash_and_check(zf, after_file, expected_hash)
    if not ok:
        return VerifyResult(ok=False, message=detail, manifest_version=2, timestamp_status=status)

    if status != "timestamped":
        return VerifyResult(
            ok=True,
            message="NO TIMESTAMP — this pack has no independent timestamp; content hash matches",
            manifest_version=2,
            content_hash=expected_hash,
            timestamp_status=status,
        )

    token_file = fields.get("tsa_token_file")
    if not token_file or token_file not in names:
        return VerifyResult(
            ok=False,
            message="timestamp_status says timestamped but the token file is missing from the archive",
            manifest_version=2,
            timestamp_status=status,
        )

    token_bytes = zf.read(token_file)
    # Deliberately IGNORES the archive's own tsa-chain.pem — only our bundled
    # chain is ever trusted. See module docstring.
    verified = _run_openssl_verify(token_bytes, expected_hash)
    if not verified:
        return VerifyResult(
            ok=False,
            message="RFC 3161 timestamp verification failed against TrustPages' trusted CA chain",
            manifest_version=2,
            content_hash=expected_hash,
            timestamp_status=status,
        )
    return VerifyResult(
        ok=True,
        message="PASS — content hash matches and timestamp verified",
        manifest_version=2,
        content_hash=expected_hash,
        timestamp_status=status,
        tsa_authority_url=fields.get("tsa_authority_url"),
        tsa_time_utc=fields.get("tsa_time_utc"),
    )


def verify_content_and_token(content_bytes: bytes, token_bytes: bytes) -> VerifyResult:
    """No manifest at all — just a content file and its claimed .tsr token.
    Verified against TrustPages' own bundled CA chain(s) only, same as the
    whole-pack path."""
    if len(content_bytes) > MAX_UPLOAD_BYTES or len(token_bytes) > MAX_UPLOAD_BYTES:
        return VerifyResult(ok=False, message=f"file too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")

    digest = hashlib.sha256(content_bytes).hexdigest()
    if _run_openssl_verify(token_bytes, digest):
        return VerifyResult(
            ok=True,
            message="PASS — content hash matches and timestamp verified",
            content_hash=digest,
            timestamp_status="timestamped",
        )
    return VerifyResult(
        ok=False,
        message="RFC 3161 timestamp verification failed against TrustPages' trusted CA chain",
        content_hash=digest,
    )
