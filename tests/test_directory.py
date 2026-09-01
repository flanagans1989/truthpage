import json
from datetime import datetime, timezone
from types import SimpleNamespace

from app.core.llm.extractor import diff_entries
from app.core.llm.schemas import SubProcessorEntry, SubProcessorList
from app.core.vendor_seeds import VENDOR_SEEDS
from app.routers.vendors import _json_ld


class TestEntryDiff:
    def test_detects_an_addition(self):
        added, removed = diff_entries([{"name": "AWS"}], [{"name": "AWS"}, {"name": "Stripe"}])
        assert added == ["Stripe"]
        assert removed == []

    def test_detects_a_removal(self):
        added, removed = diff_entries([{"name": "AWS"}, {"name": "Twilio"}], [{"name": "AWS"}])
        assert added == []
        assert removed == ["Twilio"]

    def test_reworded_purpose_is_not_a_change(self):
        # The most common false positive: a vendor rewrites the purpose column
        # and every row looks new. Names alone decide.
        added, removed = diff_entries(
            [{"name": "AWS", "purpose": "hosting"}],
            [{"name": "AWS", "purpose": "cloud hosting and storage"}],
        )
        assert (added, removed) == ([], [])

    def test_case_and_padding_do_not_create_changes(self):
        added, removed = diff_entries([{"name": "Stripe"}], [{"name": " stripe "}])
        assert (added, removed) == ([], [])

    def test_first_extraction_reports_everything_as_added(self):
        added, removed = diff_entries(None, [{"name": "AWS"}, {"name": "Stripe"}])
        assert added == ["AWS", "Stripe"]
        assert removed == []

    def test_blank_names_are_ignored(self):
        added, removed = diff_entries([], [{"name": "  "}, {"purpose": "x"}])
        assert (added, removed) == ([], [])

    def test_result_is_sorted_for_stable_rendering(self):
        added, _ = diff_entries([], [{"name": "Zulip"}, {"name": "Airtable"}])
        assert added == ["Airtable", "Zulip"]


class TestExtractionSchema:
    def test_entry_defaults_are_empty_not_invented(self):
        entry = SubProcessorEntry(name="AWS")
        assert entry.purpose == ""
        assert entry.location == ""

    def test_a_page_with_no_list_is_representable(self):
        assert SubProcessorList().entries == []


class TestJsonLd:
    def _vendor(self, **overrides):
        defaults = dict(
            slug="stripe",
            name="Stripe",
            monitored_url="https://stripe.com/legal/service-providers",
            homepage_url="https://stripe.com",
            entries=[{"name": "AWS"}, {"name": "Twilio"}],
            entries_updated_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        )
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_is_valid_json_and_a_schema_org_dataset(self):
        data = json.loads(_json_ld(self._vendor(), []))
        assert data["@context"] == "https://schema.org"
        assert data["@type"] == "Dataset"

    def test_names_the_organisation_it_is_about(self):
        data = json.loads(_json_ld(self._vendor(), []))
        assert data["about"]["@type"] == "Organization"
        assert data["about"]["name"] == "Stripe"

    def test_cites_the_source_page(self):
        data = json.loads(_json_ld(self._vendor(), []))
        assert data["isBasedOn"] == "https://stripe.com/legal/service-providers"

    def test_lists_every_extracted_entry(self):
        data = json.loads(_json_ld(self._vendor(), []))
        assert [v["name"] for v in data["variableMeasured"]] == ["AWS", "Twilio"]

    def test_date_modified_tracks_the_extraction(self):
        data = json.loads(_json_ld(self._vendor(), []))
        assert data["dateModified"] == "2026-09-02"

    def test_no_date_modified_before_a_first_extraction(self):
        data = json.loads(_json_ld(self._vendor(entries_updated_at=None), []))
        assert "dateModified" not in data

    def test_temporal_coverage_spans_the_recorded_changes(self):
        changes = [
            SimpleNamespace(created_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
            SimpleNamespace(created_at=datetime(2026, 7, 4, tzinfo=timezone.utc)),
        ]
        data = json.loads(_json_ld(self._vendor(), changes))
        assert data["temporalCoverage"] == "2026-07-04/2026-09-01"

    def test_homepage_is_omitted_rather_than_faked(self):
        data = json.loads(_json_ld(self._vendor(homepage_url=None), []))
        assert "url" not in data["about"]


class TestVendorSeeds:
    def test_slugs_are_unique(self):
        slugs = [s["slug"] for s in VENDOR_SEEDS]
        assert len(slugs) == len(set(slugs))

    def test_slugs_are_url_safe(self):
        for s in VENDOR_SEEDS:
            assert s["slug"] == s["slug"].lower()
            assert " " not in s["slug"]
            assert "/" not in s["slug"]

    def test_every_seed_has_a_name_and_an_https_source(self):
        for s in VENDOR_SEEDS:
            assert s["name"].strip()
            assert s["monitored_url"].startswith("https://"), s["slug"]
