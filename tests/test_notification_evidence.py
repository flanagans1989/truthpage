"""app/services/evidence.py's [REVIEW]/[NOTIFICATION]/[OBJECTION WINDOW]
sections, notice.txt/delivery_log.csv in the ZIP, and the redacted/full
delivery-log variant — the PR 4 half of the manifest schema frozen in
docs/manifest_v2.md. Uses the same SimpleNamespace fixture style as
test_evidence_export.py (which this file complements, not replaces).
"""
import csv as csv_module
import hashlib
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.services.evidence import (
    NOT_AVAILABLE,
    evidence_zip,
    parse_manifest_v2,
)

APP_URL = "https://usetrustpages.com/"


def _tenant(**overrides):
    defaults = dict(name="Acme Inc.", slug="acme")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _delivery_event(event_type: str, occurred_at: datetime):
    return SimpleNamespace(event_type=event_type, occurred_at=occurred_at)


def _recipient(email: str, *, events=None, resend_message_id="msg-1", **overrides):
    defaults = dict(
        recipient_email=email,
        resend_message_id=resend_message_id,
        send_error=None,
        manually_resolved_at=None,
        manually_resolved_by=None,
        manually_resolved_note=None,
        last_manual_resend_at=None,
        delivery_events=events or [],
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _objection(**overrides):
    defaults = dict(
        objector_name="Jane Customer",
        objected_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
        note="Called to object.",
        recorded_by_email="owner@acme.com",
        created_at=datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _base_event(**overrides):
    now = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)
    defaults = dict(
        id=UUID("11111111-2222-3333-4444-555555555555"),
        created_at=now,
        subprocessor=SimpleNamespace(name="Cloudflare", monitored_url="https://cloudflare.example.com"),
        llm_classification="MATERIAL",
        llm_confidence=0.91,
        llm_summary="Added a new hosting sub-processor.",
        status="approved",
        approved_by="trustpages",
        approved_at=now,
        old_hash="a" * 64,
        new_hash="b" * 64,
        raw_diff="--- before\n+++ after\n-Old\n+New",
        old_content_text="Old page text.",
        new_content_text="New page text.",
        old_raw_html="<html>old</html>",
        new_raw_html="<html>new</html>",
        old_raw_html_hash="c" * 64,
        new_raw_html_hash="d" * 64,
        notice_subject="[OBJECTION WINDOW]-day notice",
        notice_body="draft body",
        # PR 4 fields:
        reviewed_by_name="Jane Reviewer",
        reviewed_by_email="owner@acme.com",
        reviewed_at=now,
        review_action="notice_released_by_reviewer",
        notice_frozen_subject="A sub-processor changed",
        notice_frozen_body="Hello,\n\nA vendor changed. You have 30 days, write to owner@acme.com.\n",
        notice_frozen_at=now,
        notified_at=now,
        recipient_count=2,
        window_days=30,
        window_closes_at=now + timedelta(days=30),
        notification_recipients=[
            _recipient("sub1@example.com", events=[_delivery_event("delivered", now)]),
            _recipient("sub2@example.com", events=[_delivery_event("bounced", now)]),
        ],
        objections=[],
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _zip_files(zip_bytes: bytes) -> dict[str, str]:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        return {name: zf.read(name).decode("utf-8") for name in zf.namelist()}


class TestReviewSection:
    def test_reviewer_identity_and_action_are_real_values(self):
        manifest = _zip_files(evidence_zip(_base_event(), APP_URL, _tenant()))["manifest.txt"]
        fields = parse_manifest_v2(manifest)
        assert fields["reviewed_by_name"] == "Jane Reviewer"
        assert fields["reviewed_by_email"] == "owner@acme.com"
        assert fields["review_action"] == "notice_released_by_reviewer"
        assert fields["reviewed_at"] != NOT_AVAILABLE

    def test_cosmetic_auto_publish_has_no_reviewer(self):
        event = _base_event(
            reviewed_by_name=None, reviewed_by_email=None, reviewed_at=None,
            review_action="auto_published_cosmetic",
            notice_frozen_subject=None, notice_frozen_body=None, notice_frozen_at=None,
            recipient_count=None, notified_at=None, window_days=None, window_closes_at=None,
            notification_recipients=[],
        )
        manifest = _zip_files(evidence_zip(event, APP_URL, _tenant()))["manifest.txt"]
        fields = parse_manifest_v2(manifest)
        assert fields["reviewed_by_name"] == NOT_AVAILABLE
        assert fields["review_action"] == "auto_published_cosmetic"


class TestNotificationSection:
    def test_real_values_and_counts(self):
        manifest = _zip_files(evidence_zip(_base_event(), APP_URL, _tenant()))["manifest.txt"]
        fields = parse_manifest_v2(manifest)
        assert fields["recipient_count"] == "2"
        assert fields["delivered_count"] == "1"
        assert fields["bounced_count"] == "1"
        assert fields["notice_file"] == "notice.txt"
        assert fields["delivery_log_file"] == "delivery_log.csv"
        assert fields["sent_at"] != NOT_AVAILABLE

    def test_no_recipients_is_not_available(self):
        event = _base_event(
            notice_frozen_subject=None, notice_frozen_body=None, notice_frozen_at=None,
            recipient_count=0, notified_at=None, window_days=None, window_closes_at=None,
            notification_recipients=[],
        )
        manifest = _zip_files(evidence_zip(event, APP_URL, _tenant()))["manifest.txt"]
        fields = parse_manifest_v2(manifest)
        assert fields["recipient_count"] == NOT_AVAILABLE
        assert fields["delivered_count"] == NOT_AVAILABLE
        assert fields["delivery_log_file"] == NOT_AVAILABLE
        assert "delivery_log.csv" not in _zip_files(evidence_zip(event, APP_URL, _tenant()))
        assert "notice.txt" not in _zip_files(evidence_zip(event, APP_URL, _tenant()))

    def test_notice_txt_contains_the_frozen_text_not_the_editable_draft(self):
        event = _base_event(notice_subject="EDITABLE DRAFT SUBJECT", notice_body="EDITABLE DRAFT BODY")
        files = _zip_files(evidence_zip(event, APP_URL, _tenant()))
        assert "A sub-processor changed" in files["notice.txt"]
        assert "EDITABLE DRAFT" not in files["notice.txt"]


class TestDeliveryLogVariant:
    def test_redacted_is_the_default_and_masks_addresses(self):
        files = _zip_files(evidence_zip(_base_event(), APP_URL, _tenant()))
        assert "delivery_log.csv" in files
        assert "delivery_log_full.csv" not in files
        rows = list(csv_module.reader(StringIO(files["delivery_log.csv"])))
        emails = [row[0] for row in rows[1:]]
        assert all("@" in e and not e.startswith("sub1") for e in emails)
        assert any(e.startswith("s***@") for e in emails)

    def test_full_variant_uses_a_different_filename_and_real_addresses(self):
        files = _zip_files(evidence_zip(_base_event(), APP_URL, _tenant(), delivery_variant="full"))
        assert "delivery_log_full.csv" in files
        assert "delivery_log.csv" not in files
        rows = list(csv_module.reader(StringIO(files["delivery_log_full.csv"])))
        emails = {row[0] for row in rows[1:]}
        assert emails == {"sub1@example.com", "sub2@example.com"}

    def test_manifest_names_whichever_file_was_actually_produced(self):
        manifest = _zip_files(
            evidence_zip(_base_event(), APP_URL, _tenant(), delivery_variant="full")
        )["manifest.txt"]
        fields = parse_manifest_v2(manifest)
        assert fields["delivery_log_file"] == "delivery_log_full.csv"

    def test_pack_contents_hash_matches_whichever_variant_was_built(self):
        files = _zip_files(evidence_zip(_base_event(), APP_URL, _tenant(), delivery_variant="full"))
        fields = parse_manifest_v2(files["manifest.txt"])
        expected = hashlib.sha256(files["delivery_log_full.csv"].encode("utf-8")).hexdigest()
        assert fields["pack_contents"]["delivery_log_full.csv"] == expected


class TestObjectionWindowSection:
    def test_open_window_no_objections(self):
        event = _base_event(window_closes_at=datetime.now(timezone.utc) + timedelta(days=10))
        manifest = _zip_files(evidence_zip(event, APP_URL, _tenant()))["manifest.txt"]
        fields = parse_manifest_v2(manifest)
        assert fields["window_days"] == "30"
        assert fields["window_source"] == "tenant configuration (default 30)"
        assert fields["objection_status"].startswith("Window open")

    def test_custom_window_days_reads_as_an_override(self):
        event = _base_event(window_days=45, window_closes_at=datetime.now(timezone.utc) + timedelta(days=10))
        manifest = _zip_files(evidence_zip(event, APP_URL, _tenant()))["manifest.txt"]
        fields = parse_manifest_v2(manifest)
        assert fields["window_source"] == "tenant configuration (45 days, default 30)"

    def test_recorded_objection_overrides_open_window_status(self):
        event = _base_event(
            window_closes_at=datetime.now(timezone.utc) + timedelta(days=10),
            objections=[_objection()],
        )
        manifest = _zip_files(evidence_zip(event, APP_URL, _tenant()))["manifest.txt"]
        fields = parse_manifest_v2(manifest)
        assert fields["objection_status"] == "1 objection(s) recorded"

    def test_no_recipients_is_not_available_not_a_false_negative(self):
        event = _base_event(
            notice_frozen_subject=None, notice_frozen_body=None, notice_frozen_at=None,
            recipient_count=0, notified_at=None, window_days=None, window_closes_at=None,
            notification_recipients=[], objections=[],
        )
        manifest = _zip_files(evidence_zip(event, APP_URL, _tenant()))["manifest.txt"]
        fields = parse_manifest_v2(manifest)
        assert fields["objection_status"] == NOT_AVAILABLE
        assert fields["window_days"] == NOT_AVAILABLE


class TestForbiddenLanguageWithRealNotificationData:
    def test_no_forbidden_term_leaks_through_pr4s_dynamic_fields(self):
        from app.services.evidence import _FORBIDDEN_MANIFEST_TERMS

        event = _base_event(objections=[_objection(note="This looks fully compliant to me.")])
        manifest = _zip_files(evidence_zip(event, APP_URL, _tenant()))["manifest.txt"]
        # The objection's free-text note is NOT part of manifest.txt itself
        # (it lives in the dashboard/DB, not the frozen evidence document),
        # so this is really asserting the REVIEW/NOTIFICATION/OBJECTION
        # WINDOW sections stay clean regardless of what's recorded elsewhere.
        lower = manifest.lower()
        for term in _FORBIDDEN_MANIFEST_TERMS:
            assert term not in lower


class TestPackContentsStillConsistent:
    def test_every_file_still_has_a_schema_counterpart(self):
        files = _zip_files(evidence_zip(_base_event(), APP_URL, _tenant()))
        fields = parse_manifest_v2(files["manifest.txt"])
        evidence_file_values = {
            value for key, value in fields.items()
            if key.endswith("_file") and value != NOT_AVAILABLE
        }
        known_utility_files = {"manifest.sha256", "README.txt", "verify.sh"}
        for name in fields["pack_contents"]:
            assert name in evidence_file_values or name in known_utility_files
