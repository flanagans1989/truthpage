"""Some sub-processor lists are a static PDF, not a web page — Slack,
Heroku and Salesforce all resolve to one Salesforce-hosted PDF, and it is
a common shape generally (Okta's rotating dated PDFs are the other one,
deliberately left unmonitored — see app/core/vendor_seeds.py).

httpx hands back raw PDF bytes as `.text`, which is meaningless to
normalizer.py — it's built for HTML. This module extracts the PDF's text
and repackages it as a minimal HTML document, one `<p>` per line, so the
rest of the pipeline (normalize → hash → diff → LLM extractor) runs
unmodified: normalizer.py already treats `<p>` as a line break, which is
what keeps a diff to "this row changed" instead of "the whole document
changed" (see NORMALIZER_VERSION's history in normalizer.py).
"""
import io
from html import escape

from pypdf import PdfReader

# A scanned/image-only PDF decodes to ~nothing; let content_health's
# existing empty_content check catch that rather than inventing a second
# threshold here.


def is_pdf_response(content_type: str, url: str) -> bool:
    """Content-Type is the real signal; the URL check is a fallback for a
    server that mislabels it (seen on more than one legal/compliance CDN)."""
    if "application/pdf" in content_type.lower():
        return True
    return url.split("?", 1)[0].lower().endswith(".pdf")


def extract_pdf_text(data: bytes) -> str:
    """Raises on a corrupt or encrypted-without-empty-password PDF — the
    caller's existing broad `except Exception` around fetch_raw_html treats
    that exactly like any other fetch failure, no special-casing needed."""
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        reader.decrypt("")  # most of these are just permission-locked, not secret
    pages_text = (page.extract_text() or "" for page in reader.pages)
    return "\n".join(pages_text)


def pdf_text_as_html(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    body = "\n".join(f"<p>{escape(line)}</p>" for line in lines)
    return f"<html><body>{body}</body></html>"
