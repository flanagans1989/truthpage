import csv
import hashlib
import zipfile
from datetime import datetime, timezone
from io import BytesIO, StringIO
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.services.evidence import (
    COLUMNS,
    NOT_AVAILABLE,
    ForbiddenManifestLanguageError,
    _FORBIDDEN_MANIFEST_TERMS,
    detect_manifest_version,
    display_utc,
    evidence_csv,
    evidence_zip,
    iso_utc,
    parse_manifest_v2,
    validate_objection_status,
    validate_review_action,
)

APP_URL = "https://usetrustpages.com/"


def _tenant(**overrides):
    defaults = dict(name="Acme Inc.", slug="acme")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


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
        files = _zip_files(evidence_zip(_event(), APP_URL, _tenant()))
        assert files["before.html"] == "<html>old</html>"
        assert files["after.html"] == "<html>new</html>"
        assert files["before.txt"] == "Old page text."
        assert files["after.txt"] == "New page text."
        assert "New line" in files["diff.txt"]

    def test_missing_raw_html_is_a_note_not_a_missing_file(self):
        event = _event(old_raw_html=None, new_raw_html=None)
        files = _zip_files(evidence_zip(event, APP_URL, _tenant()))
        assert "Not captured" in files["before.html"]
        assert "Not captured" in files["after.html"]

    def test_bundle_includes_a_readme(self):
        files = _zip_files(evidence_zip(_event(), APP_URL, _tenant()))
        assert "README" in files["README.txt"]
        assert len(files["README.txt"].splitlines()) <= 20


class TestDisplayUtc:
    def test_formats_for_a_human_reader(self):
        assert display_utc(datetime(2026, 9, 2, 11, 59, 0, tzinfo=timezone.utc)) == "2026-09-02 11:59 UTC"

    def test_missing_timestamp_is_empty(self):
        assert display_utc(None) == ""


class TestManifestV2Schema:
    """PR 2 test items 1-2: every field present, unknowns are literally
    not_available — never omitted, never blank, never guessed at."""

    _REQUIRED_FIELDS = (
        "manifest_version", "generated_at", "generator",
        "tenant_name", "trust_page_url", "subprocessor_name", "source_url", "change_id",
        "detected_at", "previous_snapshot_captured_at", "current_snapshot_captured_at",
        "classification", "classifier_model", "classifier_note",
        "hash_algorithm", "before_html_file", "before_sha256", "after_html_file",
        "after_sha256", "before_text_file", "before_text_sha256",
        "after_text_file", "after_text_sha256", "diff_file", "diff_sha256",
        "timestamp_status", "tsa_token_file", "tsa_authority_url", "tsa_time_utc",
        "tsa_chain_file", "verification_instructions",
        "reviewed_by_name", "reviewed_by_email", "reviewed_at", "review_action",
        "notice_frozen_at", "notice_file", "sent_at", "recipient_count",
        "delivered_count", "bounced_count", "delivery_log_file",
        "window_days", "window_source", "window_opened_at", "window_closes_at",
        "objection_status",
    )
    _REQUIRED_SECTIONS = (
        "[NOTICE]", "[SUBJECT]", "[DETECTION]", "[EVIDENCE]", "[TIMESTAMP]",
        "[REVIEW]", "[NOTIFICATION]", "[OBJECTION WINDOW]", "[PACK CONTENTS]",
    )

    def _manifest(self, **event_overrides):
        files = _zip_files(evidence_zip(_event(**event_overrides), APP_URL, _tenant()))
        return files["manifest.txt"], files

    def test_every_documented_field_is_present(self):
        manifest, _ = self._manifest()
        fields = parse_manifest_v2(manifest)
        for name in self._REQUIRED_FIELDS:
            assert name in fields, f"missing field: {name}"

    def test_every_documented_section_header_is_present(self):
        manifest, _ = self._manifest()
        for header in self._REQUIRED_SECTIONS:
            assert header in manifest

    def test_fields_this_pr_cannot_fill_read_not_available_verbatim(self):
        manifest, _ = self._manifest()
        fields = parse_manifest_v2(manifest)
        for name in (
            "previous_snapshot_captured_at", "timestamp_status", "tsa_token_file",
            "reviewed_by_name", "review_action", "notice_file", "window_days",
            "objection_status",
        ):
            assert fields[name] == NOT_AVAILABLE

    def test_todays_available_fields_carry_the_real_values(self):
        manifest, _ = self._manifest()
        fields = parse_manifest_v2(manifest)
        assert fields["tenant_name"] == "Acme Inc."
        assert fields["trust_page_url"] == "https://usetrustpages.com/trust/acme"
        assert fields["subprocessor_name"] == "Cloudflare"
        assert fields["classification"] == "MATERIAL"
        assert fields["before_sha256"] == "c" * 64
        assert fields["after_sha256"] == "d" * 64
        assert fields["change_id"] == "11111111-2222-3333-4444-555555555555"

    def test_the_two_text_fields_carry_real_values_today_not_available(self):
        # before.txt/after.txt already exist on every event — unlike the
        # TIMESTAMP/REVIEW/NOTIFICATION/OBJECTION WINDOW sections, there's
        # no reason for these to read not_available.
        manifest, _ = self._manifest()
        fields = parse_manifest_v2(manifest)
        assert fields["before_text_file"] == "before.txt"
        assert fields["after_text_file"] == "after.txt"
        assert fields["before_text_sha256"] == hashlib.sha256(b"Old page text.").hexdigest()
        assert fields["after_text_sha256"] == hashlib.sha256(b"New page text.").hexdigest()

    def test_manifest_is_always_english_regardless_of_ui_language(self):
        # No locale plumbing exists in evidence_zip at all — asserting the
        # literal fixed English section headers is the guard against one
        # ever being added without updating this pin.
        manifest, _ = self._manifest()
        assert "[NOTICE]" in manifest and "[HINWEIS]" not in manifest


class TestManifestDeterminism:
    def test_the_same_event_produces_byte_identical_manifests(self):
        event = _event()
        first = _zip_files(evidence_zip(event, APP_URL, _tenant()))["manifest.txt"]
        second = _zip_files(evidence_zip(event, APP_URL, _tenant()))["manifest.txt"]
        assert first == second


class TestPackContents:
    def test_every_listed_hash_matches_the_real_file_in_the_zip(self):
        files = _zip_files(evidence_zip(_event(), APP_URL, _tenant()))
        manifest = files["manifest.txt"]
        fields = parse_manifest_v2(manifest)
        for name, expected_hash in fields["pack_contents"].items():
            actual = hashlib.sha256(files[name].encode("utf-8")).hexdigest()
            assert actual == expected_hash, f"{name}: pack_contents hash does not match the actual file"

    def test_manifest_itself_is_not_in_its_own_pack_contents_list(self):
        files = _zip_files(evidence_zip(_event(), APP_URL, _tenant()))
        fields = parse_manifest_v2(files["manifest.txt"])
        assert "manifest.txt" not in fields["pack_contents"]

    def test_manifest_sha256_is_a_separate_file_matching_manifest_txt(self):
        files = _zip_files(evidence_zip(_event(), APP_URL, _tenant()))
        expected = hashlib.sha256(files["manifest.txt"].encode("utf-8")).hexdigest()
        assert files["manifest.sha256"].strip() == expected

    def test_every_pack_file_has_a_schema_counterpart(self):
        # No file may sit in the ZIP unexplained — an auditor's "what is
        # this file" question must have an answer in manifest.txt. The
        # EVIDENCE section's *_file fields name the evidentiary documents;
        # manifest.sha256 and README.txt are the two documented utility
        # files (see docs/manifest_v2.md), not evidence, so they're the
        # only files allowed to lack an EVIDENCE *_file counterpart.
        files = _zip_files(evidence_zip(_event(), APP_URL, _tenant()))
        fields = parse_manifest_v2(files["manifest.txt"])
        evidence_file_values = {
            fields["before_html_file"], fields["after_html_file"],
            fields["before_text_file"], fields["after_text_file"],
            fields["diff_file"],
        }
        known_utility_files = {"manifest.sha256", "README.txt"}
        for name in fields["pack_contents"]:
            assert name in evidence_file_values or name in known_utility_files, (
                f"{name} is in the ZIP but named by no schema field"
            )


class TestForbiddenLanguage:
    def test_no_forbidden_term_appears_in_a_real_manifest(self):
        manifest = _zip_files(evidence_zip(_event(), APP_URL, _tenant()))["manifest.txt"]
        lower = manifest.lower()
        for term in _FORBIDDEN_MANIFEST_TERMS:
            assert term not in lower, f"forbidden term leaked into the manifest: {term!r}"

    def test_the_generator_itself_refuses_to_emit_a_forbidden_term(self):
        import app.services.evidence as evidence_mod

        with pytest.raises(ForbiddenManifestLanguageError):
            evidence_mod._assert_no_forbidden_terms("This change is fully GDPR compliant.")


class TestObjectionStatusValidator:
    @pytest.mark.parametrize("text", [
        "Window open (closes 2026-10-01T00:00:00Z)",
        "No objection recorded via TrustPages as of 2026-10-01T00:00:00Z",
        "0 objection(s) recorded",
        "3 objection(s) recorded",
        "not_available",
    ])
    def test_the_four_permitted_forms_pass(self, text):
        assert validate_objection_status(text) == text

    @pytest.mark.parametrize("text", [
        "Approved",
        "Compliant",
        "Window closed",
        "",
        "No objections",
    ])
    def test_anything_else_raises(self, text):
        with pytest.raises(ValueError):
            validate_objection_status(text)


class TestReviewActionValidator:
    @pytest.mark.parametrize("text", [
        "notice_released_by_reviewer",
        "auto_published_cosmetic",
        "not_available",
    ])
    def test_the_permitted_values_pass(self, text):
        assert validate_review_action(text) == text

    @pytest.mark.parametrize("text", [
        "approved_for_notification",  # the old, rejected value
        "approved",
        "Approved",
        "compliant",
        "",
    ])
    def test_anything_else_raises(self, text):
        with pytest.raises(ValueError):
            validate_review_action(text)


class TestManifestVersionDetection:
    def test_a_v2_manifest_is_detected_as_2(self):
        manifest = _zip_files(evidence_zip(_event(), APP_URL, _tenant()))["manifest.txt"]
        assert detect_manifest_version(manifest) == 2

    def test_a_manifest_with_no_version_field_is_treated_as_v1(self):
        v1_manifest = (
            "TrustPages — audit evidence for one detected change\n"
            "=======================================================\n\n"
            "Sub-processor:        Cloudflare\n"
        )
        assert detect_manifest_version(v1_manifest) == 1

    def test_v1_packs_are_never_regenerated_or_upgraded(self):
        # There is no function anywhere in this module that takes v1 text
        # and returns v2 text — detect_manifest_version only classifies.
        # This test exists as an explicit trip-wire: it fails the moment
        # such a function gets added, forcing that decision to be visible
        # in review rather than sliding in as a refactor.
        import app.services.evidence as evidence_mod

        assert not hasattr(evidence_mod, "upgrade_manifest")
        assert not hasattr(evidence_mod, "migrate_manifest")
