"""Rendering of the audit artifact: change events as CSV, or as a per-event ZIP.

Kept out of the router so the exact shape of the file — column order, time
format, what is quoted — can be asserted without a database. An auditor reads
this file; a silent change to a column is a change to the evidence.

The ZIP's manifest.txt follows the frozen schema in docs/manifest_v2.md —
field names, order and section headers there are the spec; this module is
one implementation of it, not the other way around.
"""
from collections.abc import Iterable
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any
import csv
import hashlib
import re
import zipfile

from app.core.llm.analyzer import _MODEL as _CLASSIFIER_MODEL
from app.db.models.mixins import utc_now

COLUMNS = (
    "detected_at_utc",
    "sub_processor",
    "monitored_url",
    "classification",
    "confidence",
    "summary",
    "status",
    "decided_by",
    "decided_at_utc",
    "subscribers_notified_at_utc",
    "content_hash_before",
    "content_hash_after",
    "evidence_record",
)


def iso_utc(value: datetime | None) -> str:
    """ISO-8601 UTC. A spreadsheet's locale must not be able to change what an
    evidence record says happened when."""
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value is not None else ""


def _row(event: Any, app_url: str) -> list[str]:
    return [
        iso_utc(event.created_at),
        event.subprocessor.name,
        event.subprocessor.monitored_url,
        event.llm_classification or "",
        f"{event.llm_confidence:.2f}" if event.llm_confidence is not None else "",
        # Newlines inside a cell survive CSV quoting but wreck the file in most
        # spreadsheet importers, so the summary is flattened to one line.
        (event.llm_summary or "").replace("\r", " ").replace("\n", " "),
        event.status,
        event.approved_by or "",
        iso_utc(event.approved_at),
        iso_utc(event.notified_at),
        event.old_hash,
        event.new_hash,
        f"{app_url.rstrip('/')}/dashboard/events/{event.id}",
    ]


def evidence_csv(events: Iterable[Any], app_url: str) -> str:
    """Full change history as CSV.

    Page bodies are deliberately excluded: they run to tens of thousands of
    characters and would make the file unreadable. Each row carries both
    hashes and the URL of the record that holds the documents themselves.
    """
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(COLUMNS)
    for event in events:
        writer.writerow(_row(event, app_url))
    return buffer.getvalue()


def display_utc(value: datetime | None) -> str:
    """Human-facing UTC stamp for the manifest's anchor box, e.g.
    '2026-09-02 11:59 UTC'. iso_utc() above stays the machine-readable form
    used in the CSV; this one is what a person reads in the ZIP."""
    return value.strftime("%Y-%m-%d %H:%M UTC") if value is not None else ""


MANIFEST_VERSION = 2
# Keep in sync with pyproject.toml's [project].version — there's no runtime
# way to read one from the other without adding a packaging dependency, and
# this changes rarely enough that a comment is the honest cost.
GENERATOR_VERSION = "0.1.0"
NOT_AVAILABLE = "not_available"

# A hard rule (see docs/manifest_v2.md): this document reports facts and
# digests, never a legal conclusion. Checked at generation time as well as
# by tests — a mistake here should never reach a real download.
_FORBIDDEN_MANIFEST_TERMS = (
    "compliant",
    "uyumlu",
    "approved",
    "onaylandı",
    "valid consent",
    "gdpr compliant",
    "meets article 28",
)


class ForbiddenManifestLanguageError(ValueError):
    """A manifest was about to assert a legal conclusion it has no business making."""


def _assert_no_forbidden_terms(manifest_text: str) -> None:
    lower = manifest_text.lower()
    for term in _FORBIDDEN_MANIFEST_TERMS:
        if term in lower:
            raise ForbiddenManifestLanguageError(
                f"manifest.txt would contain the forbidden term {term!r} — "
                "this document may only report facts and digests."
            )


# The only sentences [OBJECTION WINDOW]'s objection_status may hold. Not
# used to fill anything in this PR (the section stays not_available until
# PR 4), but frozen and enforced now so PR 4 has no room to phrase a status
# as a legal conclusion.
_OBJECTION_STATUS_PATTERNS = (
    re.compile(r"^Window open \(closes .+\)$"),
    re.compile(r"^No objection recorded via TrustPages as of .+$"),
    re.compile(r"^\d+ objection\(s\) recorded$"),
    re.compile(rf"^{re.escape(NOT_AVAILABLE)}$"),
)


def validate_objection_status(text: str) -> str:
    """Returns `text` unchanged if it matches one of the four permitted
    objection_status shapes; raises ValueError otherwise. Anything else
    ("Approved", "Compliant", free text) could read as this document
    drawing a legal conclusion, which it never does."""
    if any(pattern.match(text) for pattern in _OBJECTION_STATUS_PATTERNS):
        return text
    raise ValueError(f"objection_status is not one of the four permitted forms: {text!r}")


def _sha256(content: str | bytes | None) -> str:
    if content is None:
        return NOT_AVAILABLE
    data = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(data).hexdigest()


def _na(value: Any) -> str:
    return str(value) if value not in (None, "") else NOT_AVAILABLE


def _render_manifest_v2(event: Any, app_url: str, tenant: Any, pack_files: dict[str, str]) -> str:
    """Builds manifest.txt per docs/manifest_v2.md. Every field the schema
    lists is always present — a value TrustPages cannot supply today is
    `not_available`, literally, never omitted and never guessed at.

    `pack_files` maps every OTHER file's exact bytes-as-written by name —
    [PACK CONTENTS] hashes what's actually in the ZIP, not a value computed
    separately from it, so the two can never quietly drift apart.
    """
    now = utc_now()
    trust_page_url = f"{app_url.rstrip('/')}/trust/{tenant.slug}"

    diff_text = event.raw_diff or ""
    detected_at = iso_utc(event.created_at)

    lines = [
        "TrustPages Audit Evidence Pack",
        f"manifest_version: {MANIFEST_VERSION}",
        f"generated_at: {iso_utc(now)}",
        f"generator: TrustPages {GENERATOR_VERSION}",
        "",
        "[NOTICE]",
        "This pack records observed facts and cryptographic digests. It is not a",
        "legal opinion and does not assert compliance with any regulation.",
        "",
        "[SUBJECT]",
        f"tenant_name: {_na(tenant.name)}",
        f"trust_page_url: {trust_page_url}",
        f"subprocessor_name: {_na(event.subprocessor.name)}",
        f"source_url: {_na(event.subprocessor.monitored_url)}",
        f"change_id: {_na(event.id)}",
        "",
        "[DETECTION]",
        f"detected_at: {detected_at or NOT_AVAILABLE}",
        # Not stored per-event today — the pipeline only records the moment
        # a change was detected, not a separate "previous capture" instant.
        # Adding that is a data-collection decision outside this PR's scope.
        f"previous_snapshot_captured_at: {NOT_AVAILABLE}",
        f"current_snapshot_captured_at: {detected_at or NOT_AVAILABLE}",
        f"classification: {_na(event.llm_classification)}",
        f"classifier_model: {_CLASSIFIER_MODEL}",
        "classifier_note: Automated assessment. Not a legal determination.",
        "",
        "[EVIDENCE]",
        # before_sha256/after_sha256 read the digest TrustPages computed at
        # capture time (ContentHasher, same SHA-256-over-UTF-8 algorithm as
        # _sha256() below) rather than re-hashing pack_files here — the two
        # agree exactly whenever the capture was real (same bytes, same
        # algorithm), and diverge on purpose when it wasn't: [PACK CONTENTS]
        # still hashes whatever placeholder text is physically in the ZIP
        # (a real digest of "Not captured for this change."), while this
        # section correctly says not_available rather than dignifying a
        # placeholder note as evidence.
        "hash_algorithm: SHA-256",
        "before_html_file: before.html",
        f"before_sha256: {_na(event.old_raw_html_hash)}",
        "after_html_file: after.html",
        f"after_sha256: {_na(event.new_raw_html_hash)}",
        "diff_file: diff.txt",
        f"diff_sha256: {_sha256(diff_text) if diff_text else NOT_AVAILABLE}",
        # The current (after) normalized text — the "raw" pre-diff text
        # extracted from after.html — paired the same way after_sha256 is;
        # before.txt is still present in the pack and listed under [PACK
        # CONTENTS] below, just without its own named EVIDENCE field.
        "raw_text_file: after.txt",
        f"raw_text_sha256: {_sha256(event.new_content_text)}",
        "",
        "[TIMESTAMP]",
        f"timestamp_status: {NOT_AVAILABLE}",
        f"tsa_token_file: {NOT_AVAILABLE}",
        f"tsa_authority_url: {NOT_AVAILABLE}",
        f"tsa_time_utc: {NOT_AVAILABLE}",
        f"tsa_chain_file: {NOT_AVAILABLE}",
        "verification_instructions: See README.txt — run ./verify.sh offline.",
        "",
        "[REVIEW]",
        f"reviewed_by_name: {NOT_AVAILABLE}",
        f"reviewed_by_email: {NOT_AVAILABLE}",
        f"reviewed_at: {NOT_AVAILABLE}",
        f"review_action: {NOT_AVAILABLE}",
        "",
        "[NOTIFICATION]",
        f"notice_frozen_at: {NOT_AVAILABLE}",
        f"notice_file: {NOT_AVAILABLE}",
        f"sent_at: {NOT_AVAILABLE}",
        f"recipient_count: {NOT_AVAILABLE}",
        f"delivered_count: {NOT_AVAILABLE}",
        f"bounced_count: {NOT_AVAILABLE}",
        f"delivery_log_file: {NOT_AVAILABLE}",
        "",
        "[OBJECTION WINDOW]",
        f"window_days: {NOT_AVAILABLE}",
        f"window_source: {NOT_AVAILABLE}",
        f"window_opened_at: {NOT_AVAILABLE}",
        f"window_closes_at: {NOT_AVAILABLE}",
        f"objection_status: {validate_objection_status(NOT_AVAILABLE)}",
        "",
        "[PACK CONTENTS]",
    ]
    for name in sorted(pack_files, key=str.lower):
        lines.append(f"{name}  {pack_files[name]}")
    lines.append("")

    text = "\n".join(lines)
    _assert_no_forbidden_terms(text)
    return text


def _readme_v2() -> str:
    """Plain-English orientation for whoever opens this ZIP without the
    TrustPages dashboard in front of them. Kept under 20 lines on purpose —
    the manifest is the reference document, this just points at it."""
    return "\n".join([
        "TrustPages Audit Evidence Pack — README",
        "",
        "manifest.txt describes every file in this ZIP and its SHA-256 digest.",
        "manifest.sha256 is the digest of manifest.txt itself.",
        "",
        "Files:",
        "  before.html / after.html — raw HTML fetched from the vendor's page",
        "  before.txt  / after.txt  — normalized text extracted from that HTML",
        "  diff.txt                — unified diff between before.txt and after.txt",
        "",
        "To verify a file: compute its SHA-256 and compare it to the value",
        "manifest.txt lists for that file. Any mismatch means the file has",
        "changed since this pack was generated.",
        "",
        "This pack does NOT independently prove *when* the capture happened —",
        "packs generated before RFC 3161 timestamping shipped have no",
        "independent timestamp ([TIMESTAMP] section reads not_available).",
        "A future TrustPages release adds ./verify.sh for offline verification.",
        "",
        "This pack states observed facts and digests. It is not a legal opinion.",
    ]) + "\n"


def evidence_zip(event: Any, app_url: str, tenant: Any) -> bytes:
    """One detected change as a self-contained ZIP: the documents on both
    sides of it, the diff, and a manifest describing all of it — everything
    an auditor asks for, without having to trust a page rendering it
    correctly. manifest.txt follows docs/manifest_v2.md; `tenant` supplies
    the SUBJECT section's tenant identity (deliberately passed in rather
    than read off `event.subprocessor.tenant`, which isn't eager-loaded on
    every caller today).

    Missing pieces (an event recorded before raw HTML was captured) become
    `not_available` in the manifest, never a missing file silently
    swallowed — before.html/after.html etc. are always present, with a note
    where the real content isn't.
    """
    pack_files = {
        "before.html": event.old_raw_html or "Not captured for this change.",
        "after.html": event.new_raw_html or "Not captured for this change.",
        "before.txt": event.old_content_text or "Not captured for this change.",
        "after.txt": event.new_content_text or "Not captured for this change.",
        "diff.txt": event.raw_diff or "",
        "README.txt": _readme_v2(),
    }
    pack_hashes = {name: _sha256(content) for name, content in pack_files.items()}

    manifest_text = _render_manifest_v2(event, app_url, tenant, pack_hashes)
    manifest_sha256 = _sha256(manifest_text)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.txt", manifest_text)
        zf.writestr("manifest.sha256", manifest_sha256 + "\n")
        for name, content in pack_files.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def detect_manifest_version(manifest_text: str) -> int:
    """1 if manifest_text has no `manifest_version` field (every pack
    generated before this schema existed), else the integer the field
    names. Existing v1 packs must stay verifiable forever — this is the
    branch point any future reader (this app's, or a third party's) uses,
    never a re-generation or upgrade of the old text."""
    match = re.search(r"^manifest_version:\s*(\d+)\s*$", manifest_text, re.MULTILINE)
    return int(match.group(1)) if match else 1


def parse_manifest_v2(manifest_text: str) -> dict[str, Any]:
    """Flat field-name → value dict for a v2 manifest, plus a nested
    `pack_contents` dict of filename → sha256 from [PACK CONTENTS]. Field
    names are unique across sections in this schema, so a flat dict is
    enough — a future /verify page reads specific fields out of this
    rather than re-parsing the text itself."""
    fields: dict[str, Any] = {}
    pack_contents: dict[str, str] = {}
    in_pack_contents = False

    for raw_line in manifest_text.splitlines():
        line = raw_line.rstrip("\n")
        if not line:
            continue
        if line.startswith("["):
            in_pack_contents = line.strip() == "[PACK CONTENTS]"
            continue
        if line.startswith("TrustPages Audit Evidence Pack"):
            continue
        if in_pack_contents:
            parts = line.split()
            if len(parts) == 2:
                pack_contents[parts[0]] = parts[1]
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()

    fields["pack_contents"] = pack_contents
    return fields
