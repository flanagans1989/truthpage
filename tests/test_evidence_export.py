import csv
from datetime import datetime, timezone
from io import StringIO
from types import SimpleNamespace
from uuid import UUID

from app.services.evidence import COLUMNS, evidence_csv, iso_utc

APP_URL = "https://usetrustpages.com/"


def _event(**overrides):
    defaults = dict(
        id=UUID("11111111-2222-3333-4444-555555555555"),
        created_at=datetime(2026, 9, 1, 7, 5, 9, tzinfo=timezone.utc),
        subprocessor=SimpleNamespace(
            name="Cloudflare",
            monitored_url="https://www.cloudflare.com/gdpr/subprocessors/cloudflare-services/",
        ),
        llm_classification="MATERIAL",
        llm_confidence=0.91,
        llm_summary="Added a new hosting sub-processor.",
        status="approved",
        approved_by="trustpages",
        approved_at=datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc),
        notified_at=datetime(2026, 9, 1, 9, 0, 30, tzinfo=timezone.utc),
        old_hash="a" * 64,
        new_hash="b" * 64,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _rows(csv_text: str) -> list[list[str]]:
    return list(csv.reader(StringIO(csv_text)))


class TestIsoUtc:
    def test_formats_as_zulu(self):
        assert iso_utc(datetime(2026, 9, 1, 7, 5, 9, tzinfo=timezone.utc)) == "2026-09-01T07:05:09Z"

    def test_missing_timestamp_is_empty(self):
        assert iso_utc(None) == ""


class TestEvidenceCsv:
    def test_header_is_the_documented_column_order(self):
        assert _rows(evidence_csv([], APP_URL))[0] == list(COLUMNS)

    def test_empty_history_still_produces_a_header(self):
        assert len(_rows(evidence_csv([], APP_URL))) == 1

    def test_row_carries_the_audit_fields(self):
        row = _rows(evidence_csv([_event()], APP_URL))[1]
        cells = dict(zip(COLUMNS, row))
        assert cells["detected_at_utc"] == "2026-09-01T07:05:09Z"
        assert cells["sub_processor"] == "Cloudflare"
        assert cells["classification"] == "MATERIAL"
        assert cells["confidence"] == "0.91"
        assert cells["status"] == "approved"
        assert cells["decided_by"] == "trustpages"
        assert cells["decided_at_utc"] == "2026-09-01T09:00:00Z"
        assert cells["subscribers_notified_at_utc"] == "2026-09-01T09:00:30Z"
        assert cells["content_hash_before"] == "a" * 64
        assert cells["content_hash_after"] == "b" * 64

    def test_record_url_has_no_double_slash(self):
        row = _rows(evidence_csv([_event()], APP_URL))[1]
        assert row[-1] == (
            "https://usetrustpages.com/dashboard/events/"
            "11111111-2222-3333-4444-555555555555"
        )

    def test_undecided_event_leaves_decision_cells_empty(self):
        event = _event(
            status="pending_review",
            approved_by=None,
            approved_at=None,
            notified_at=None,
            llm_confidence=None,
            llm_summary=None,
        )
        cells = dict(zip(COLUMNS, _rows(evidence_csv([event], APP_URL))[1]))
        assert cells["decided_by"] == ""
        assert cells["decided_at_utc"] == ""
        assert cells["subscribers_notified_at_utc"] == ""
        assert cells["confidence"] == ""
        assert cells["summary"] == ""

    def test_multiline_summary_is_flattened_to_one_row(self):
        event = _event(llm_summary="Line one.\nLine two.\r\nLine three.")
        rows = _rows(evidence_csv([event], APP_URL))
        assert len(rows) == 2
        assert "\n" not in dict(zip(COLUMNS, rows[1]))["summary"]

    def test_every_event_produces_exactly_one_row(self):
        rows = _rows(evidence_csv([_event(), _event(), _event()], APP_URL))
        assert len(rows) == 4
