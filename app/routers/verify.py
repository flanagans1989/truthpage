"""Public, unauthenticated, no-account audit evidence verification.

Everything here is processed in memory and discarded when the request
ends — nothing uploaded is written to permanent disk, logged, or looked up
against the database. See app/services/verify.py's module docstring for
the full list of hard rules this endpoint exists to honor.
"""
import logging

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse

from app.core.ratelimit import SlidingWindowLimiter, get_client_ip
from app.core.templating import templates as _templates
from app.services.verify import (
    MAX_UPLOAD_BYTES,
    VerifyResult,
    verify_content_and_token,
    verify_pack,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["verify"])

# Generous enough for someone re-checking a pack after fixing an upload
# mistake; tight enough that this can't become free CPU for a stranger.
_verify_limiter = SlidingWindowLimiter(max_requests=10, window_seconds=60)

# Read in chunks with an early abort — never fully buffer a claimed-huge
# upload just to reject it after the fact.
_READ_CHUNK_BYTES = 65_536


async def _read_capped(file: UploadFile, max_bytes: int) -> bytes | None:
    """None means "too large" — aborted before finishing the read."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/verify", response_class=HTMLResponse)
async def verify_form(request: Request):
    return _templates.TemplateResponse(request, "verify.html", {"result": None, "error": None})


@router.post("/verify", response_class=HTMLResponse)
async def verify_submit(
    request: Request,
    pack: UploadFile | None = File(None),
    content: UploadFile | None = File(None),
    token: UploadFile | None = File(None),
):
    client_ip = get_client_ip(request)
    if not _verify_limiter.allow(f"ip:{client_ip}"):
        return _templates.TemplateResponse(
            request, "verify.html",
            {"result": None, "error": "Too many requests — try again in a minute."},
            status_code=429,
        )

    # Never log which branch, filenames, or any content — only that a
    # verification request happened and, at most, its coarse outcome.
    if pack is not None and pack.filename:
        pack_bytes = await _read_capped(pack, MAX_UPLOAD_BYTES)
        if pack_bytes is None:
            result = VerifyResult(ok=False, message=f"file too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
        else:
            result = verify_pack(pack_bytes)
    elif content is not None and content.filename and token is not None and token.filename:
        content_bytes = await _read_capped(content, MAX_UPLOAD_BYTES)
        token_bytes = await _read_capped(token, MAX_UPLOAD_BYTES)
        if content_bytes is None or token_bytes is None:
            result = VerifyResult(ok=False, message=f"file too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
        else:
            result = verify_content_and_token(content_bytes, token_bytes)
    else:
        return _templates.TemplateResponse(
            request, "verify.html",
            {"result": None, "error": "Upload either the whole .zip, or a content file and its .tsr token."},
        )

    logger.info("verify: request from %s — ok=%s", client_ip, result.ok)
    return _templates.TemplateResponse(request, "verify.html", {"result": result, "error": None})
