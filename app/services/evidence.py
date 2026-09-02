"""Rendering of the audit artifact: change events as CSV, or as a per-event ZIP.

Kept out of the router so the exact shape of the file — column order, time
format, what is quoted — can be asserted without a database. An auditor reads
this file; a silent change to a column is a change to the evidence.
"""
from collections.abc import Iterable
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any
import csv
import zipfile

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


def _manifest(event: Any, app_url: str) -> str:
    """The one file in the ZIP meant to be read, not diffed against.

    Plain text on purpose — the bundle has to open the same way on an
    auditor's machine ten years from now, with no app to render it in.
    """
    lines = [
        "TrustPages — audit evidence for one detected change",
        "=" * 55,
        "",
        f"Sub-processor:        {event.subprocessor.name}",
        f"Monitored URL:         {event.subprocessor.monitored_url}",
        f"Change detected:       {iso_utc(event.created_at)}",
        f"Classification:        {event.llm_classification or 'not classified'}"
        + (f" ({event.llm_confidence:.0%} confidence)" if event.llm_confidence is not None else ""),
        f"Status:                {event.status}",
        f"Content hash before:   {event.old_hash}",
        f"Content hash after:    {event.new_hash}",
        f"Decision:              "
        + (
            f"{event.approved_by or 'unknown'} at {iso_utc(event.approved_at)}"
            if event.approved_at is not None
            else "no manual decision recorded (auto-published)"
            if event.status == "auto_published"
            else "not yet decided"
        ),
        f"Subscribers notified:  {iso_utc(event.notified_at) or 'not notified'}",
        "",
        "Summary",
        "-" * 55,
        event.llm_summary or "(none)",
        "",
        "Article 28(2) customer notice",
        "-" * 55,
    ]
    if event.notice_body:
        lines += [
            f"Subject: {event.notice_subject or ''}",
            "",
            event.notice_body,
        ]
    else:
        lines.append("No notice has been drafted for this change yet.")
    lines += [
        "",
        "Files in this bundle",
        "-" * 55,
        "before.html / after.html — raw HTML as fetched from the vendor's page",
        "before.txt  / after.txt  — normalized text used for the diff below",
        "diff.txt                — unified diff between the two",
        "",
        f"Full record: {app_url.rstrip('/')}/dashboard/events/{event.id}",
    ]
    return "\n".join(lines) + "\n"


def evidence_zip(event: Any, app_url: str) -> bytes:
    """One detected change as a self-contained ZIP: the documents on both
    sides of it, the diff, and the decision/notice trail — everything an
    auditor asks for, without having to trust a page rendering it correctly.

    Missing pieces (an event recorded before raw HTML was captured, or before
    a notice was drafted) become a note in the manifest, never a missing file
    silently swallowed.
    """
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.txt", _manifest(event, app_url))
        zf.writestr("before.html", event.old_raw_html or "Not captured for this change.")
        zf.writestr("after.html", event.new_raw_html or "Not captured for this change.")
        zf.writestr("before.txt", event.old_content_text or "Not captured for this change.")
        zf.writestr("after.txt", event.new_content_text or "Not captured for this change.")
        zf.writestr("diff.txt", event.raw_diff or "")
    return buffer.getvalue()
