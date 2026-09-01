"""Rendering of the audit artifact: change events as CSV.

Kept out of the router so the exact shape of the file — column order, time
format, what is quoted — can be asserted without a database. An auditor reads
this file; a silent change to a column is a change to the evidence.
"""
from collections.abc import Iterable
from datetime import datetime
from io import StringIO
from typing import Any
import csv

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
