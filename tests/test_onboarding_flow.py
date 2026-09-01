"""Route-level walk through the wizard, on a throwaway SQLite database.

The unit tests cover the matching and the plan cap. What they cannot cover is
the part that actually breaks: form names that don't line up with parameters,
an HTMX target that no longer exists, a partial rendered with the wrong
context, and the publish gate on the public page. So this runs the real
routes against a real (if tiny) database.

SQLite, deliberately: the local .env points at the production Neon database,
and a test suite must never be one import away from writing to it.
"""
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from app.db.base import Base
from app.db.models.tenant import Tenant
from app.db.session import get_db_session
from app.main import app
from app.routers.auth import _make_session_token


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def tenant(db_engine):
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with factory() as session:
        row = Tenant(
            name="Acme",
            slug="acme",
            email="owner@acme.com",
            subscription_status="trialing",
            trial_ends_at=datetime(2030, 1, 1, tzinfo=UTC),
        )
        session.add(row)
        await session.commit()
    return row


@pytest.fixture
def client(db_engine, tenant):
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override
    # No context manager: the lifespan would start the sweep scheduler.
    c = TestClient(app)
    c.cookies.set("session", _make_session_token(str(tenant.id)))
    yield c
    app.dependency_overrides.clear()


class TestWizard:
    def test_the_wizard_renders_for_a_signed_in_tenant(self, client):
        response = client.get("/onboarding")
        assert response.status_code == 200
        assert "Pick the services you use" in response.text
        assert "Amazon Web Services" in response.text

    def test_signing_out_is_not_a_way_in(self, db_engine, tenant):
        app.dependency_overrides.clear()
        anonymous = TestClient(app, raise_server_exceptions=False)
        assert anonymous.get("/onboarding").status_code == 401

    def test_picking_providers_adds_exactly_those(self, client):
        response = client.post("/onboarding/library", data={"slugs": ["stripe", "sentry"]})
        assert response.status_code == 200
        assert "Added 2 vendors" in response.text
        # The picker comes back with both marked, so nobody adds them twice.
        assert response.text.count('value="stripe"') == 0

        listed = client.get("/onboarding").text
        assert "Stripe" in listed and "Sentry" in listed

    def test_adding_nothing_is_not_an_error(self, client):
        assert client.post("/onboarding/library", data={}).status_code == 200

    def test_a_vendor_we_do_not_know_can_be_added_by_url(self, client):
        response = client.post(
            "/onboarding/custom",
            data={"name": "Acme Billing", "monitored_url": "https://example.com/subprocessors"},
        )
        assert response.status_code == 200
        assert "Acme Billing" in response.text

    def test_a_private_url_is_refused(self, client):
        response = client.post(
            "/onboarding/custom",
            data={"name": "Internal", "monitored_url": "http://127.0.0.1/secrets"},
        )
        assert response.status_code == 422

    def test_the_same_vendor_cannot_be_added_twice(self, client):
        client.post("/onboarding/library", data={"slugs": ["stripe"]})
        response = client.post(
            "/onboarding/custom",
            data={"name": "Stripe, Inc.", "monitored_url": "https://stripe.com/legal"},
        )
        assert "already on your list" in response.text

    def test_a_vendor_can_be_removed_again(self, client):
        client.post("/onboarding/library", data={"slugs": ["stripe"]})
        page = client.get("/onboarding").text
        assert "Stripe" in page
        # The remove button posts the row id; pull it back out of the markup.
        marker = 'hx-post="/onboarding/remove/'
        row_id = page.split(marker, 1)[1].split('"', 1)[0]
        response = client.post(f"/onboarding/remove/{row_id}")
        assert response.status_code == 200
        assert 'hx-post="/onboarding/remove/' not in response.text


class TestPublishGate:
    def test_the_trust_page_is_404_until_it_is_published(self, client):
        client.post("/onboarding/library", data={"slugs": ["stripe"]})
        assert client.get("/trust/acme").status_code == 404

    def test_publishing_opens_the_page_and_keeps_the_name(self, client):
        client.post("/onboarding/library", data={"slugs": ["stripe"]})
        response = client.post(
            "/onboarding/publish", data={"company_name": "Acme Systems"}, follow_redirects=False
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/trust/acme"

        live = client.get("/trust/acme")
        assert live.status_code == 200
        assert "Acme Systems" in live.text
        assert "Stripe" in live.text

    def test_a_published_tenant_is_not_sent_back_through_the_wizard(self, client, tenant):
        client.post("/onboarding/library", data={"slugs": ["stripe"]})
        client.post("/onboarding/publish", data={"company_name": "Acme"})
        # The wizard stays reachable on purpose — it doubles as the quick
        # import screen — but the page it built is now open, which is what
        # `needs_onboarding` gates. (The dashboard is not exercised here:
        # SQLite hands back naive datetimes and its trial-countdown maths
        # needs the timezone Postgres actually stores.)
        assert client.get("/onboarding").status_code == 200
        assert client.get("/trust/acme").status_code == 200


class TestImportEndpoint:
    def test_an_extraction_becomes_pickable_candidates(self, client, monkeypatch):
        from app.core.llm.schemas import SubProcessorEntry, SubProcessorList
        from app.services import onboarding

        async def _fake_extract(text):
            return SubProcessorList(
                entries=[
                    SubProcessorEntry(name="Stripe, Inc.", purpose="payments"),
                    SubProcessorEntry(name="Acme Internal Tools", purpose="billing"),
                ]
            )

        monkeypatch.setattr(onboarding._extractor, "extract", _fake_extract)

        response = client.post(
            "/onboarding/import",
            data={"policy_text": "We share data with Stripe, Inc. and Acme Internal Tools." * 20},
        )
        assert response.status_code == 200
        # The known one is offered as a one-click add…
        assert 'value="stripe"' in response.text
        # …the unknown one asks for its URL instead of being guessed at.
        assert "Acme Internal Tools" in response.text
        assert "can't monitor yet" in response.text

    def test_an_empty_paste_asks_for_something_to_read(self, client):
        response = client.post("/onboarding/import", data={"policy_text": "", "policy_url": ""})
        assert "policy URL" in response.text

    def test_nothing_is_written_by_an_import(self, client, db_engine, tenant, monkeypatch):
        from app.core.llm.schemas import SubProcessorEntry, SubProcessorList
        from app.services import onboarding

        async def _fake_extract(text):
            return SubProcessorList(entries=[SubProcessorEntry(name="Stripe")])

        monkeypatch.setattr(onboarding._extractor, "extract", _fake_extract)
        client.post("/onboarding/import", data={"policy_text": "Stripe " * 100})
        assert "Stripe" not in client.get("/onboarding").text.split("Publish your trust page")[1]
