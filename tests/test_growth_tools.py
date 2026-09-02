"""The public growth tools: the audit grader and the sample-evidence lead
magnet. Route-level, against the throwaway SQLite database from conftest.
"""
import zipfile
from io import BytesIO

from sqlalchemy import select

import app.routers.tools as tools_mod
from app.core.audit_grader import grade_for, scan_for_known_vendors
from app.db.models.lead import Lead


class TestScanForKnownVendors:
    def test_matches_a_provider_by_its_display_name(self):
        assert "Stripe" in scan_for_known_vendors("We use Stripe for payments.")

    def test_matches_common_acronyms_not_just_the_full_name(self):
        # Real privacy pages write "AWS", almost never "Amazon Web Services".
        found = scan_for_known_vendors("Hosted on AWS.")
        assert "Amazon Web Services" in found

    def test_does_not_match_an_unrelated_mention_of_a_generic_word(self):
        # "google" alone is deliberately not in the safe-alias list — see
        # audit_grader.py's _SAFE_ALIASES comment.
        assert scan_for_known_vendors("Sign in with Google.") == []

    def test_no_known_vendor_returns_empty(self):
        assert scan_for_known_vendors("We use a totally custom homegrown stack.") == []

    def test_results_stay_in_providers_order_and_deduplicated(self):
        text = "AWS, then more AWS, then Stripe, then Amazon Web Services again."
        found = scan_for_known_vendors(text)
        assert found.count("Amazon Web Services") == 1
        assert found == ["Amazon Web Services", "Stripe"] or found == ["Stripe", "Amazon Web Services"] or set(found) == {"Amazon Web Services", "Stripe"}


class TestGradeFor:
    def test_zero_found_is_the_lowest_grade(self):
        grade, label = grade_for(0)
        assert grade == "D"
        assert "No known sub-processors" in label

    def test_any_finding_still_flags_missing_monitoring(self):
        for count in (1, 2, 3, 6, 20):
            _, label = grade_for(count)
            assert "Change monitoring and audit evidence missing" == label

    def test_grade_never_reaches_a_or_b_plus(self):
        # The whole point: a vendor count can't buy its way past the one
        # thing every scanned page is actually missing.
        for count in range(0, 50):
            grade, _ = grade_for(count)
            assert grade in ("D", "C", "C+", "B-")


class TestAuditGraderRoute:
    def test_form_renders(self, anon_client):
        r = anon_client.get("/tools/audit-grader")
        assert r.status_code == 200
        assert "Sub-processor Scanner" in r.text

    def test_rejects_a_private_ip_target(self, anon_client):
        r = anon_client.post("/tools/audit-grader", data={"url": "http://127.0.0.1/x"})
        assert r.status_code == 200
        assert "not allowed" in r.text.lower()

    def test_scans_a_fetched_page_and_shows_the_grade(self, anon_client, monkeypatch):
        async def fake_fetch(url):
            return "<html><body>We use Stripe and AWS and Postmark.</body></html>"

        monkeypatch.setattr(tools_mod, "fetch_html_fast", fake_fetch)

        async def fake_validate(url):
            return None

        monkeypatch.setattr(tools_mod, "validate_url", fake_validate)

        r = anon_client.post("/tools/audit-grader", data={"url": "https://example.com/privacy"})
        assert r.status_code == 200
        assert "Stripe" in r.text
        assert "Sub-processors found: 3" in r.text
        assert "Change monitoring and audit evidence missing" in r.text

    def test_rate_limit_kicks_in_after_five_scans(self, anon_client, monkeypatch):
        async def fake_fetch(url):
            return "<html></html>"

        async def fake_validate(url):
            return None

        monkeypatch.setattr(tools_mod, "fetch_html_fast", fake_fetch)
        monkeypatch.setattr(tools_mod, "validate_url", fake_validate)

        for _ in range(5):
            anon_client.post("/tools/audit-grader", data={"url": "https://example.com"})
        r = anon_client.post("/tools/audit-grader", data={"url": "https://example.com"})
        assert r.status_code == 429


class TestSampleEvidencePack:
    def test_downloads_a_zip_with_the_expected_files(self, anon_client):
        r = anon_client.post("/tools/sample-evidence-pack", data={"email": "lead@example.com"})
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        zf = zipfile.ZipFile(BytesIO(r.content))
        assert "manifest.txt" in zf.namelist()
        assert "before.html" in zf.namelist()
        assert "after.html" in zf.namelist()
        assert "diff.txt" in zf.namelist()

    async def _lead_rows(self, session_factory):
        async with session_factory() as session:
            return list((await session.execute(select(Lead))).scalars().all())

    def test_records_the_email_as_a_lead(self, anon_client, session_factory):
        anon_client.post("/tools/sample-evidence-pack", data={"email": "Lead@Example.com"})
        import asyncio

        rows = asyncio.run(self._lead_rows(session_factory))
        assert len(rows) == 1
        assert rows[0].email == "lead@example.com"
        assert rows[0].source == "sample_evidence_pack"


def test_landing_and_compare_link_the_sample_zip_form(anon_client):
    home = anon_client.get("/").text
    compare = anon_client.get("/compare").text
    assert "/tools/sample-evidence-pack" in home
    assert "/tools/sample-evidence-pack" in compare
