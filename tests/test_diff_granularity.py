"""The diff was structurally incapable of showing what changed.

normalize() collapsed every newline into a space; detector.py then ran
splitlines() over the result, which on a document with no newlines returns
one element. difflib was therefore always comparing two one-line "files",
and its only possible output was "the whole document was deleted, the
whole document was added" — for a typo exactly as much as for a new
sub-processor. That made every evidence pack's diff.txt unreadable and
turned the 12k cut fed to the classifier into a blind crop of the OLD
document.
"""
from app.core.scraper.detector import ChangeDetector, diff_for_llm
from app.core.scraper.normalizer import HTMLNormalizer

_n = HTMLNormalizer()
_d = ChangeDetector()

BEFORE = _n.normalize(
    "<body><h1>Sub-processors</h1><table>"
    "<tr><td>AWS</td><td>Hosting</td></tr>"
    "<tr><td>Stripe</td><td>Payments</td></tr>"
    "<tr><td>Twilio</td><td>SMS</td></tr>"
    "</table></body>"
)
AFTER = _n.normalize(
    "<body><h1>Sub-processors</h1><table>"
    "<tr><td>AWS</td><td>Hosting</td></tr>"
    "<tr><td>Stripe</td><td>Payments</td></tr>"
    "<tr><td>Acme Analytics</td><td>Product analytics</td></tr>"
    "<tr><td>Twilio</td><td>SMS</td></tr>"
    "</table></body>"
)


def test_one_added_vendor_is_one_added_line():
    diff = _d.unified_diff(BEFORE, AFTER, label="acme")
    added = [ln for ln in diff.split("\n") if ln.startswith("+") and not ln.startswith("+++")]
    removed = [ln for ln in diff.split("\n") if ln.startswith("-") and not ln.startswith("---")]

    assert added == ["+Acme Analytics Product analytics"]
    # The regression this pins: nothing was removed, so nothing may be
    # reported as removed. The old normalizer reported the entire document.
    assert removed == []


def test_unchanged_lines_survive_as_context():
    diff = _d.unified_diff(BEFORE, AFTER, label="acme")
    assert " AWS Hosting" in diff.split("\n")


def test_identical_content_produces_no_diff():
    assert _d.unified_diff(BEFORE, BEFORE) == ""


def _long_diff(change_at_the_end: bool) -> str:
    filler_before = [f"Vendor {i} purpose {i}" for i in range(800)]
    filler_after = list(filler_before)
    if change_at_the_end:
        filler_after.append("Acme Analytics Product analytics")
    else:
        filler_after.insert(0, "Acme Analytics Product analytics")
    return _d.unified_diff("\n".join(filler_before), "\n".join(filler_after))


def test_a_change_at_the_end_of_a_long_page_still_reaches_the_classifier():
    """A sub-processor table is usually near the bottom, and the longest
    pages belong to the biggest vendors — so a head-crop failed hardest
    exactly where the stakes were highest."""
    trimmed = diff_for_llm(_long_diff(change_at_the_end=True), max_chars=2_000)

    assert len(trimmed) <= 2_000
    assert "+Acme Analytics Product analytics" in trimmed


def test_a_change_at_the_start_also_survives_trimming():
    trimmed = diff_for_llm(_long_diff(change_at_the_end=False), max_chars=2_000)
    assert "+Acme Analytics Product analytics" in trimmed


def test_trimming_says_so_out_loud():
    """An honest omission notice is what lets the model answer UNCERTAIN —
    which routes to human review — instead of confidently classifying a
    fragment it cannot see the rest of."""
    before = "\n".join(f"line {i}" for i in range(400))
    after = "\n".join(f"line {i} changed" if i % 7 == 0 else f"line {i}" for i in range(400))
    trimmed = diff_for_llm(_d.unified_diff(before, after), max_chars=1_500)

    assert "omitted" in trimmed
    assert len(trimmed) <= 1_500


def test_short_diffs_are_passed_through_untouched():
    diff = _d.unified_diff(BEFORE, AFTER)
    assert diff_for_llm(diff) == diff
