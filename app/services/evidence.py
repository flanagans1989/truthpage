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
from pathlib import Path
from typing import Any
import csv
import hashlib
import re
import zipfile

from app.core.config import settings
from app.core.llm.analyzer import _MODEL as _CLASSIFIER_MODEL
from app.db.models.mixins import utc_now
from app.services.notifications import compute_objection_status, derive_recipient_status, summarize_recipients

# FreeTSA's CA chain (root + signing cert) — checked into the repo, not
# fetched at runtime, so a ZIP is buildable offline and this file's content
# is exactly what verify.sh and /verify both trust. Bundled once, alongside
# app/core/tsa.py's TSA_PRIMARY_URL default.
_TSA_CHAIN_PATH = Path(__file__).parent.parent / "static_data" / "tsa" / "freetsa-chain.pem"

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


# The system records the observed action only ("released" — a human let a
# drafted notice go out, or the pipeline auto-published a cosmetic change).
# "Approved" is a legal characterization this manifest never makes — see
# docs/manifest_v2.md's [REVIEW] notes. No exception to the forbidden-terms
# check exists for this: the fix was correcting the value, not loosening
# the invariant.
_ALLOWED_REVIEW_ACTIONS = (
    "notice_released_by_reviewer",
    "auto_published_cosmetic",
    NOT_AVAILABLE,
)


def validate_review_action(text: str) -> str:
    """Returns `text` unchanged if it's one of the permitted review_action
    values; raises ValueError otherwise."""
    if text in _ALLOWED_REVIEW_ACTIONS:
        return text
    raise ValueError(f"review_action is not one of the permitted values: {text!r}")


def _sha256(content: str | bytes | None) -> str:
    if content is None:
        return NOT_AVAILABLE
    data = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(data).hexdigest()


def _na(value: Any) -> str:
    return str(value) if value not in (None, "") else NOT_AVAILABLE


def tsa_token_filename() -> str:
    """<after_html_file>.sha256.tsr — the token only ever exists for
    after.html, so the name doubles as saying which file it covers."""
    return "after.html.sha256.tsr"


def _timestamp_section_lines(event: Any) -> list[str]:
    """[TIMESTAMP]'s five real fields, ahead of the fixed
    verification_instructions line. timestamp_status is always the
    column's actual value (pending/retrying/timestamped/failed/
    not_available_pre_tsa) — never invented. The other four are
    not_available for every status except `timestamped`, where the token
    file, the CA chain file, and what the TSA itself reported are the only
    time these fields carry a value other than not_available.
    """
    status = getattr(event, "timestamp_status", None) or NOT_AVAILABLE
    lines = [f"timestamp_status: {status}"]
    if status == "timestamped":
        lines += [
            f"tsa_token_file: {tsa_token_filename()}",
            f"tsa_authority_url: {_na(getattr(event, 'tsa_authority_url', None))}",
            f"tsa_time_utc: {iso_utc(getattr(event, 'tsa_time_utc', None)) or NOT_AVAILABLE}",
            "tsa_chain_file: tsa-chain.pem",
        ]
    else:
        lines += [
            f"tsa_token_file: {NOT_AVAILABLE}",
            f"tsa_authority_url: {NOT_AVAILABLE}",
            f"tsa_time_utc: {NOT_AVAILABLE}",
            f"tsa_chain_file: {NOT_AVAILABLE}",
        ]
    return lines


def notice_filename() -> str:
    return "notice.txt"


def delivery_log_filename(variant: str) -> str:
    """delivery_log.csv (redacted, the default) or delivery_log_full.csv —
    the variant is encoded in the filename itself rather than as a new
    manifest field, since [NOTIFICATION]'s delivery_log_file already names
    whichever file is actually in the pack (see docs/manifest_v2.md's
    frozen schema — this PR does not add a field to it)."""
    return "delivery_log.csv" if variant == "redacted" else "delivery_log_full.csv"


def _review_section_lines(event: Any) -> list[str]:
    return [
        f"reviewed_by_name: {_na(getattr(event, 'reviewed_by_name', None))}",
        f"reviewed_by_email: {_na(getattr(event, 'reviewed_by_email', None))}",
        f"reviewed_at: {iso_utc(getattr(event, 'reviewed_at', None)) or NOT_AVAILABLE}",
        f"review_action: {validate_review_action(getattr(event, 'review_action', None) or NOT_AVAILABLE)}",
    ]


def _notification_section_lines(event: Any, delivery_variant: str) -> list[str]:
    recipient_count = getattr(event, "recipient_count", None)
    if not recipient_count:
        return [
            f"notice_frozen_at: {NOT_AVAILABLE}",
            f"notice_file: {NOT_AVAILABLE}",
            f"sent_at: {NOT_AVAILABLE}",
            f"recipient_count: {NOT_AVAILABLE}",
            f"delivered_count: {NOT_AVAILABLE}",
            f"bounced_count: {NOT_AVAILABLE}",
            f"delivery_log_file: {NOT_AVAILABLE}",
        ]
    recipients = getattr(event, "notification_recipients", None) or []
    counts = summarize_recipients(recipients)
    return [
        f"notice_frozen_at: {iso_utc(getattr(event, 'notice_frozen_at', None)) or NOT_AVAILABLE}",
        f"notice_file: {notice_filename()}",
        f"sent_at: {iso_utc(getattr(event, 'notified_at', None)) or NOT_AVAILABLE}",
        f"recipient_count: {recipient_count}",
        f"delivered_count: {counts['delivered_count']}",
        f"bounced_count: {counts['bounced_count']}",
        f"delivery_log_file: {delivery_log_filename(delivery_variant)}",
    ]


def _objection_window_section_lines(event: Any) -> list[str]:
    window_days = getattr(event, "window_days", None)
    if window_days is None:
        return [
            f"window_days: {NOT_AVAILABLE}",
            f"window_source: {NOT_AVAILABLE}",
            f"window_opened_at: {NOT_AVAILABLE}",
            f"window_closes_at: {NOT_AVAILABLE}",
            f"objection_status: {validate_objection_status(compute_objection_status(event))}",
        ]
    default_days = settings.DEFAULT_OBJECTION_WINDOW_DAYS
    source = (
        f"tenant configuration (default {default_days})"
        if window_days == default_days
        else f"tenant configuration ({window_days} days, default {default_days})"
    )
    return [
        f"window_days: {window_days}",
        f"window_source: {source}",
        f"window_opened_at: {iso_utc(getattr(event, 'notified_at', None)) or NOT_AVAILABLE}",
        f"window_closes_at: {iso_utc(getattr(event, 'window_closes_at', None)) or NOT_AVAILABLE}",
        f"objection_status: {validate_objection_status(compute_objection_status(event))}",
    ]


def _render_manifest_v2(
    event: Any, app_url: str, tenant: Any, pack_files: dict[str, str], delivery_variant: str = "redacted"
) -> str:
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
        # Symmetric with the HTML pair above — before.txt/after.txt are real
        # files in the pack (see [PACK CONTENTS]); every file named there
        # must have a field here explaining what it is.
        "before_text_file: before.txt",
        f"before_text_sha256: {_sha256(event.old_content_text)}",
        "after_text_file: after.txt",
        f"after_text_sha256: {_sha256(event.new_content_text)}",
        "diff_file: diff.txt",
        f"diff_sha256: {_sha256(diff_text) if diff_text else NOT_AVAILABLE}",
        "",
        "[TIMESTAMP]",
        *_timestamp_section_lines(event),
        "verification_instructions: See README.txt — run ./verify.sh offline.",
        "",
        "[REVIEW]",
        *_review_section_lines(event),
        "",
        "[NOTIFICATION]",
        *_notification_section_lines(event, delivery_variant),
        "",
        "[OBJECTION WINDOW]",
        *_objection_window_section_lines(event),
        "",
        "[PACK CONTENTS]",
    ]
    for name in sorted(pack_files, key=str.lower):
        lines.append(f"{name}  {pack_files[name]}")
    lines.append("")

    text = "\n".join(lines)
    _assert_no_forbidden_terms(text)
    return text


def _readme_v2(timestamped: bool) -> str:
    """Plain-English orientation for whoever opens this ZIP without the
    TrustPages dashboard in front of them. Kept under 25 lines on purpose —
    the manifest is the reference document, this just points at it."""
    lines = [
        "TrustPages Audit Evidence Pack — README",
        "",
        "manifest.txt describes every file in this ZIP and its SHA-256 digest.",
        "manifest.sha256 is the digest of manifest.txt itself.",
        "",
        "Files:",
        "  before.html / after.html — raw HTML fetched from the vendor's page",
        "  before.txt  / after.txt  — normalized text extracted from that HTML",
        "  diff.txt                — unified diff between before.txt and after.txt",
        "  verify.sh               — offline check: run it, needs only openssl",
    ]
    if timestamped:
        lines.append("  after.html.sha256.tsr  — RFC 3161 timestamp token for after.html's digest")
        lines.append("  tsa-chain.pem          — the timestamp authority's CA chain, for offline checking")
    lines += [
        "",
        "To verify by hand: compute a file's SHA-256 and compare it to the",
        "value manifest.txt lists for it. Easier: run ./verify.sh (openssl",
        "required; on Windows use WSL or Git Bash).",
        "",
    ]
    if timestamped:
        lines += [
            "This pack's content hash is attested by an independent third-party",
            "timestamp authority (RFC 3161) — not just TrustPages' own record.",
            "The TSA only ever received a SHA-256 digest, never the page content.",
        ]
    else:
        lines += [
            "This pack has NO independent timestamp — it predates RFC 3161",
            "timestamping, or one could not be obtained. The content hash above",
            "is still valid; only the *when* isn't independently attested.",
        ]
    lines += ["", "This pack states observed facts and digests. It is not a legal opinion."]
    return "\n".join(lines) + "\n"


def _verify_sh() -> str:
    """POSIX sh, openssl only, no network access — reads only the files
    sitting next to it. See docs/manifest_v2.md for the exact PASS/FAIL/NO
    TIMESTAMP contract this must honor."""
    return """#!/bin/sh
# TrustPages audit evidence — offline verification. Uses only openssl and
# the files in this directory; never touches the network.
set -e
cd "$(dirname "$0")"

field() { grep "^$1:" manifest.txt | sed "s/^$1: *//"; }

AFTER_FILE=$(field after_html_file)
EXPECTED_HASH=$(field after_sha256)
STATUS=$(field timestamp_status)

if [ -z "$AFTER_FILE" ] || [ ! -f "$AFTER_FILE" ]; then
    echo "FAIL - manifest.txt does not name a captured HTML file present here"
    exit 1
fi
if [ -z "$EXPECTED_HASH" ] || [ "$EXPECTED_HASH" = "not_available" ]; then
    echo "FAIL - manifest.txt has no content hash to verify against"
    exit 1
fi

ACTUAL_HASH=$(openssl dgst -sha256 -r "$AFTER_FILE" | cut -d' ' -f1)
if [ "$ACTUAL_HASH" != "$EXPECTED_HASH" ]; then
    echo "FAIL - content hash mismatch: $AFTER_FILE has changed since this pack was generated"
    exit 1
fi

if [ "$STATUS" != "timestamped" ]; then
    echo "NO TIMESTAMP - pack predates independent timestamping; content hash matches"
    exit 0
fi

TOKEN_FILE=$(field tsa_token_file)
CHAIN_FILE=$(field tsa_chain_file)
TSA_TIME=$(field tsa_time_utc)

if [ ! -f "$TOKEN_FILE" ] || [ ! -f "$CHAIN_FILE" ]; then
    echo "FAIL - timestamp_status says timestamped but the token or CA chain file is missing"
    exit 1
fi

if openssl ts -verify -in "$TOKEN_FILE" -digest "$EXPECTED_HASH" -CAfile "$CHAIN_FILE" >/dev/null 2>&1; then
    echo "PASS - content hash matches and timestamp verified ($TSA_TIME)"
    exit 0
else
    echo "FAIL - RFC 3161 timestamp verification failed"
    exit 1
fi
"""


def _redact_email(email: str) -> str:
    """j***@acme.com — the address's domain is kept (an auditor needs to
    see which organizations were notified) but the local part is reduced
    to its first character, so the redacted variant never actually
    identifies a person by their address alone."""
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{local[:1]}***@{domain}"


_DELIVERY_LOG_COLUMNS = (
    "recipient",
    "status",
    "last_event_at_utc",
    "resend_message_id",
    "manually_resolved",
    "resolution_note",
)


def _delivery_log_row(recipient: Any, variant: str) -> list[str]:
    status = derive_recipient_status(recipient)
    events = sorted(recipient.delivery_events, key=lambda e: e.occurred_at)
    last_event_at = iso_utc(events[-1].occurred_at) if events else ""
    email = recipient.recipient_email if variant == "full" else _redact_email(recipient.recipient_email)
    return [
        email,
        status,
        last_event_at,
        recipient.resend_message_id or "",
        "yes" if recipient.manually_resolved_at else "no",
        recipient.manually_resolved_note or "",
    ]


def delivery_log_csv(recipients: Iterable[Any], variant: str) -> str:
    """delivery_log.csv (variant='redacted') or delivery_log_full.csv
    (variant='full') — see delivery_log_filename() and PR 4's section 3:
    a tenant hands this pack to a DPO or an enterprise customer's security
    review, and a file full of their own customers' raw email addresses is
    a liability few would sign off on by default."""
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_DELIVERY_LOG_COLUMNS)
    for recipient in recipients:
        writer.writerow(_delivery_log_row(recipient, variant))
    return buffer.getvalue()


def evidence_zip(event: Any, app_url: str, tenant: Any, delivery_variant: str = "redacted") -> bytes:
    """One detected change as a self-contained ZIP: the documents on both
    sides of it, the diff, a manifest describing all of it, and — once
    stamped — an independent RFC 3161 timestamp token. manifest.txt follows
    docs/manifest_v2.md; `tenant` supplies the SUBJECT section's tenant
    identity (deliberately passed in rather than read off
    `event.subprocessor.tenant`, which isn't eager-loaded on every caller
    today).

    Missing pieces (an event recorded before raw HTML was captured, or not
    yet/never independently timestamped) become `not_available` in the
    manifest, never a missing file silently swallowed — before.html/
    after.html etc. are always present; the timestamp token and CA chain
    are only ever added when there is a real, granted token to include.
    """
    timestamped = getattr(event, "timestamp_status", None) == "timestamped"

    pack_files: dict[str, str | bytes] = {
        "before.html": event.old_raw_html or "Not captured for this change.",
        "after.html": event.new_raw_html or "Not captured for this change.",
        "before.txt": event.old_content_text or "Not captured for this change.",
        "after.txt": event.new_content_text or "Not captured for this change.",
        "diff.txt": event.raw_diff or "",
        "verify.sh": _verify_sh(),
        "README.txt": _readme_v2(timestamped),
    }
    if timestamped:
        tsa_token = getattr(event, "tsa_token", None)
        if tsa_token:
            pack_files[tsa_token_filename()] = tsa_token
            pack_files["tsa-chain.pem"] = _TSA_CHAIN_PATH.read_bytes()

    if getattr(event, "notice_frozen_body", None):
        pack_files[notice_filename()] = (
            f"Subject: {event.notice_frozen_subject}\n\n{event.notice_frozen_body}\n"
        )

    if getattr(event, "recipient_count", None):
        recipients = getattr(event, "notification_recipients", None) or []
        pack_files[delivery_log_filename(delivery_variant)] = delivery_log_csv(recipients, delivery_variant)

    pack_hashes = {name: _sha256(content) for name, content in pack_files.items()}

    manifest_text = _render_manifest_v2(event, app_url, tenant, pack_hashes, delivery_variant)
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
