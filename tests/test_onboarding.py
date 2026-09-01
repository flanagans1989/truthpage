from types import SimpleNamespace

import pytest

from app.core.provider_library import (
    BY_SLUG,
    CATEGORY_ORDER,
    PROVIDERS,
    grouped,
    match_provider,
    normalise_name,
)
from app.services.onboarding import Candidate, ImportResult, build_candidates


class TestProviderLibrary:
    def test_slugs_are_unique(self):
        slugs = [p["slug"] for p in PROVIDERS]
        assert len(slugs) == len(set(slugs))

    def test_every_provider_has_the_fields_the_picker_renders(self):
        for p in PROVIDERS:
            assert p["name"].strip()
            assert p["description"].strip()
            assert p["url"].startswith("https://"), p["slug"]
            assert p["category"] in CATEGORY_ORDER, p["slug"]
            assert isinstance(p["verified"], bool)

    def test_grouping_loses_nobody(self):
        assert sum(len(rows) for _, rows in grouped()) == len(PROVIDERS)

    def test_the_library_is_worth_having(self):
        # The whole premise is "you don't hunt for URLs". A handful of
        # providers would not save anyone the trip.
        assert len(PROVIDERS) >= 30


class TestNameMatching:
    @pytest.mark.parametrize(
        "written,slug",
        [
            ("Stripe", "stripe"),
            ("Stripe, Inc.", "stripe"),
            ("  stripe  ", "stripe"),
            ("Amazon Web Services", "aws"),
            ("AWS", "aws"),
            ("Google Cloud Platform", "google-cloud"),
            ("Twilio SendGrid", "sendgrid"),
            ("Cloudflare, Inc.", "cloudflare"),
            ("MongoDB Atlas", "mongodb"),
        ],
    )
    def test_recognises_how_vendors_actually_write_it(self, written, slug):
        assert match_provider(written)["slug"] == slug

    def test_an_unknown_vendor_is_not_forced_onto_a_neighbour(self):
        # A near-miss must return None, not the closest row: a wrong match
        # points the tenant's monitoring at another company's policy page.
        assert match_provider("Stripey Analytics GmbH") is None
        assert match_provider("Acme Internal Tools") is None

    def test_blank_input_matches_nothing(self):
        assert match_provider("") is None
        assert match_provider("   ") is None

    def test_legal_suffixes_are_stripped_not_just_trimmed(self):
        assert normalise_name("Postmark B.V.") == "postmark"
        assert normalise_name("Example Corp.") == "example"


class TestBuildCandidates:
    def test_a_known_vendor_comes_back_ready_to_add(self):
        [c] = build_candidates([{"name": "Stripe, Inc."}], existing=set())
        assert c.ready
        assert c.slug == "stripe"
        assert c.url == BY_SLUG["stripe"]["url"]

    def test_a_known_vendor_is_renamed_to_the_library_spelling(self):
        # Otherwise "AWS" from a policy and "Amazon Web Services" from the
        # picker sit on the same page as two different vendors.
        [c] = build_candidates([{"name": "AWS"}], existing=set())
        assert c.name == "Amazon Web Services"

    def test_an_unknown_vendor_is_offered_but_not_addable(self):
        [c] = build_candidates([{"name": "Acme Internal Tools"}], existing=set())
        assert c.url is None
        assert not c.ready
        assert c.name == "Acme Internal Tools"

    def test_something_already_monitored_is_not_offered_again(self):
        [c] = build_candidates([{"name": "Stripe"}], existing={"stripe"})
        assert c.already_added
        assert not c.ready

    def test_duplicates_within_one_policy_collapse(self):
        rows = build_candidates(
            [{"name": "Stripe"}, {"name": "Stripe, Inc."}, {"name": "stripe"}],
            existing=set(),
        )
        assert len(rows) == 1

    def test_nameless_rows_are_dropped(self):
        assert build_candidates([{"name": "  "}, {"purpose": "hosting"}], set()) == []

    def test_purpose_survives_the_trip(self):
        [c] = build_candidates(
            [{"name": "Acme", "purpose": "invoice delivery"}], existing=set()
        )
        assert c.purpose == "invoice delivery"

    def test_ready_rows_are_listed_before_ones_needing_work(self):
        rows = build_candidates(
            [{"name": "Zeta Unknown"}, {"name": "Stripe"}, {"name": "Cloudflare"}],
            existing=set(),
        )
        assert [r.ready for r in rows] == [True, True, False]


class TestImportResultBuckets:
    def _result(self):
        return ImportResult(
            candidates=[
                Candidate(name="Stripe", slug="stripe", url="https://x"),
                Candidate(name="Acme"),
                Candidate(name="Sentry", slug="sentry", url="https://y", already_added=True),
            ]
        )

    def test_each_candidate_lands_in_exactly_one_bucket(self):
        r = self._result()
        assert [c.name for c in r.ready] == ["Stripe"]
        assert [c.name for c in r.needs_url] == ["Acme"]
        assert [c.name for c in r.already_added] == ["Sentry"]


class TestPublishGate:
    """A tenant is only counted as onboarded once they have pressed Publish."""

    def test_a_fresh_tenant_needs_onboarding(self):
        from app.db.models.tenant import Tenant

        assert Tenant(name="X", slug="x").needs_onboarding is True

    def test_publishing_clears_it(self):
        from datetime import UTC, datetime

        from app.db.models.tenant import Tenant

        t = Tenant(name="X", slug="x", onboarded_at=datetime.now(UTC))
        assert t.needs_onboarding is False


class TestAddProvidersRespectsThePlan:
    """add_providers is async and touches the session, so the cap logic is
    exercised through a stand-in session that records what was added."""

    class _Session:
        def __init__(self):
            self.added = []

        def add(self, obj):
            self.added.append(obj)

        async def commit(self):
            pass

    @pytest.mark.asyncio
    async def test_picks_over_the_cap_are_refused_not_fatal(self, monkeypatch):
        from app.services import onboarding

        async def _no_existing(tenant_id, db):
            return set()

        monkeypatch.setattr(onboarding, "existing_keys", _no_existing)
        session = self._Session()
        tenant = SimpleNamespace(id=1, slug="t", subprocessor_limit=2)

        result = await onboarding.add_providers(
            ["stripe", "aws", "sentry"], tenant, session
        )

        assert result.added == ["Stripe", "Amazon Web Services"]
        assert result.refused == ["Sentry"]
        assert len(session.added) == 2

    @pytest.mark.asyncio
    async def test_an_unknown_slug_is_ignored(self, monkeypatch):
        from app.services import onboarding

        async def _no_existing(tenant_id, db):
            return set()

        monkeypatch.setattr(onboarding, "existing_keys", _no_existing)
        session = self._Session()
        tenant = SimpleNamespace(id=1, slug="t", subprocessor_limit=25)

        result = await onboarding.add_providers(["not-a-provider"], tenant, session)
        assert result.added == []
        assert session.added == []

    @pytest.mark.asyncio
    async def test_something_already_monitored_is_skipped_not_duplicated(self, monkeypatch):
        from app.services import onboarding

        async def _has_stripe(tenant_id, db):
            return {"stripe"}

        monkeypatch.setattr(onboarding, "existing_keys", _has_stripe)
        session = self._Session()
        tenant = SimpleNamespace(id=1, slug="t", subprocessor_limit=25)

        result = await onboarding.add_providers(["stripe"], tenant, session)
        assert result.skipped == ["Stripe"]
        assert session.added == []
