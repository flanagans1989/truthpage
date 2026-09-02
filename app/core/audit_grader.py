"""Known-vendor scan behind the public /tools/audit-grader page.

Deliberately no LLM call: this is an unauthenticated, no-signup tool a
stranger can hit as many times as the rate limiter allows, and a Gemini
call per visitor is a bill with no plan behind it. A substring match
against the same 32-provider list the onboarding picker already uses is
free, instant, and exactly as confident as that picker's own
no-fuzzy-match rule already requires elsewhere in this codebase — a
near-miss here would tell a visitor we found a vendor we didn't.
"""
from app.core.provider_library import PROVIDERS

# A deliberately short list, separate from match_provider's own _ALIASES:
# that table is safe because it only ever matches a string a vendor's own
# page already extracted as a sub-processor's name. This tool searches
# unstructured prose on an arbitrary company's site, where a bare "google"
# or "amazon" is far more likely to mean "Sign in with Google" or "as seen
# on Amazon" than Google Cloud or AWS. Only acronyms specific enough that a
# false hit is implausible belong here.
_SAFE_ALIASES: dict[str, str] = {
    "aws": "aws",
    "amazon web services": "aws",
    "gcp": "google-cloud",
    "google cloud": "google-cloud",
    "postmarkapp": "postmark",
}


def scan_for_known_vendors(page_text: str) -> list[str]:
    """Known providers whose name — or one of the small set of unambiguous
    short forms above, e.g. "AWS" for Amazon Web Services — appears in the
    page text, in PROVIDERS order. Case-insensitive substring match."""
    lower = page_text.lower()
    found_slugs: set[str] = set()
    for p in PROVIDERS:
        if p["name"].lower() in lower:
            found_slugs.add(p["slug"])
    for alias, slug in _SAFE_ALIASES.items():
        if alias in lower:
            found_slugs.add(slug)
    return [p["name"] for p in PROVIDERS if p["slug"] in found_slugs]


def grade_for(found_count: int) -> tuple[str, str]:
    """A grade and the one line that matters more than the grade.

    Capped at B- no matter how many known vendors turn up: the finding is
    real, but every one of these pages is missing the same thing — nobody
    is watching it for changes, and that gap doesn't shrink as the vendor
    count grows.
    """
    if found_count == 0:
        return "D", "No known sub-processors detected on this page"
    if found_count == 1:
        return "C", "Change monitoring and audit evidence missing"
    if found_count <= 3:
        return "C+", "Change monitoring and audit evidence missing"
    return "B-", "Change monitoring and audit evidence missing"
