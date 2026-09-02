import csv
import zipfile
from datetime import datetime, timezone
from io import BytesIO, StringIO
from types import SimpleNamespace
from uuid import UUID

from app.services.evidence import COLUMNS, display_utc, evidence_csv, evidence_zip, iso_utc

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
        raw_diff="--- before\n+++ after\n-Old line\n+New line",
        old_content_text="Old page text.",
        new_content_text="New page text.",
        old_raw_html="<html>old</html>",
        new_raw_html="<html>new</html>",
        old_raw_html_hash="c" * 64,
        new_raw_html_hash="d" * 64,
        notice_subject=None,
        notice_body=None,
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


def _zip_files(zip_bytes: bytes) -> dict[str, str]:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        return {name: zf.read(name).decode("utf-8") for name in zf.namelist()}


class TestEvidenceZip:
    def test_bundle_contains_before_after_and_diff(self):
        files = _zip_files(evidence_zip(_event(), APP_URL))
        assert files["before.html"] == "<html>old</html>"
        assert files["after.html"] == "<html>new</html>"
        assert files["before.txt"] == "Old page text."
        assert files["after.txt"] == "New page text."
        assert "New line" in files["diff.txt"]

    def test_manifest_carries_the_audit_fields(self):
        manifest = _zip_files(evidence_zip(_event(), APP_URL))["manifest.txt"]
        assert "Cloudflare" in manifest
        assert "a" * 64 in manifest and "b" * 64 in manifest
        assert "MATERIAL" in manifest
        assert "trustpages" in manifest
        assert "11111111-2222-3333-4444-555555555555" in manifest

    def test_missing_raw_html_is_a_note_not_a_missing_file(self):
        event = _event(old_raw_html=None, new_raw_html=None)
        files = _zip_files(evidence_zip(event, APP_URL))
        assert "Not captured" in files["before.html"]
        assert "Not captured" in files["after.html"]

    def test_undrafted_notice_says_so_in_the_manifest(self):
        manifest = _zip_files(evidence_zip(_event(), APP_URL))["manifest.txt"]
        assert "No notice has been drafted" in manifest

    def test_drafted_notice_is_included_in_the_manifest(self):
        event = _event(notice_subject="Update to our sub-processor list", notice_body="We are adding Cloudflare.")
        manifest = _zip_files(evidence_zip(event, APP_URL))["manifest.txt"]
        assert "Update to our sub-processor list" in manifest
        assert "We are adding Cloudflare." in manifest

    def test_no_decision_yet_reads_as_not_decided(self):
        event = _event(status="pending_review", approved_at=None, approved_by=None)
        manifest = _zip_files(evidence_zip(event, APP_URL))["manifest.txt"]
        assert "not yet decided" in manifest

    def test_auto_published_with_no_decision_is_not_reported_as_undecided(self):
        event = _event(status="auto_published", approved_at=None, approved_by=None)
        manifest = _zip_files(evidence_zip(event, APP_URL))["manifest.txt"]
        assert "auto-published" in manifest


class TestDisplayUtc:
    def test_formats_for_a_human_reader(self):
        assert display_utc(datetime(2026, 9, 2, 11, 59, 0, tzinfo=timezone.utc)) == "2026-09-02 11:59 UTC"

    def test_missing_timestamp_is_empty(self):
        assert display_utc(None) == ""


class TestCryptographicAnchor:
    def test_anchor_carries_source_url_timestamp_hash_and_status(self):
        manifest = _zip_files(evidence_zip(_event(), APP_URL))["manifest.txt"]
        anchor = manifest.split("Cryptographic verification anchor")[1]
        assert "https://www.cloudflare.com/gdpr/subprocessors/cloudflare-services/" in anchor
        assert "2026-09-01 07:05 UTC" in anchor
        assert "d" * 64 in anchor
        assert "Cryptographically verified" in anchor

    def test_missing_hash_reports_not_available_rather_than_faking_it(self):
        event = _event(new_raw_html_hash=None)
        anchor = _zip_files(evidence_zip(event, APP_URL))["manifest.txt"].split("Cryptographic verification anchor")[1]
        assert "not captured for this change" in anchor
        assert "Not available" in anchor
        assert "Cryptographically verified" not in anchor

    def test_previous_capture_hash_is_included(self):
        anchor = _zip_files(evidence_zip(_event(), APP_URL))["manifest.txt"].split("Cryptographic verification anchor")[1]
        assert "c" * 64 in anchor
