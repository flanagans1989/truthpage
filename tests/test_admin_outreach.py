"""Admin-only Outreach Generator: auth gate, and a mocked-Gemini happy path.

Route-level, against the throwaway SQLite database — the Gemini call itself
is monkeypatched out, same reasoning as the notice-draft tests: a real call
would need a live key and make the suite non-deterministic.
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from app.core.llm.schemas import OutreachDraft, OutreachTemplate
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
async def admin_tenant(db_engine):
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with factory() as session:
        row = Tenant(name="Admin", slug="admin", email="admin@usetrustpages.com", subscription_status="active")
        session.add(row)
        await session.commit()
    return row


@pytest_asyncio.fixture
async def plain_tenant(db_engine):
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with factory() as session:
        row = Tenant(name="Someone", slug="someone", email="someone@else.com", subscription_status="active")
        session.add(row)
        await session.commit()
    return row


def _client(db_engine, monkeypatch, admin_emails="admin@usetrustpages.com"):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ADMIN_EMAILS", admin_emails)
    factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


class TestAuthGate:
    def test_a_non_admin_gets_404_not_403(self, db_engine, plain_tenant, monkeypatch):
        client = next(_client(db_engine, monkeypatch))
        client.cookies.set("session", _make_session_token(str(plain_tenant.id)))
        r = client.get("/admin/outreach")
        assert r.status_code == 404

    def test_signed_out_gets_401(self, db_engine, monkeypatch):
        client = next(_client(db_engine, monkeypatch))
        r = client.get("/admin/outreach")
        assert r.status_code == 401

    def test_the_admin_email_gets_the_form(self, db_engine, admin_tenant, monkeypatch):
        client = next(_client(db_engine, monkeypatch))
        client.cookies.set("session", _make_session_token(str(admin_tenant.id)))
        r = client.get("/admin/outreach")
        assert r.status_code == 200
        assert "Outreach Generator" in r.text


class TestOutreachGeneration:
    def test_drafts_three_templates_in_both_languages(self, db_engine, admin_tenant, monkeypatch):
        client = next(_client(db_engine, monkeypatch))
        client.cookies.set("session", _make_session_token(str(admin_tenant.id)))

        fake_draft = OutreachDraft(
            templates=[
                OutreachTemplate(
                    approach="Direct compliance gap", channel="email",
                    subject_en="Quick question about Acme's sub-processors",
                    subject_de="Kurze Frage zu Acmes Unterauftragsverarbeitern",
                    body_en="Hi Lena, ...", body_de="Hallo Lena, ...",
                ),
                OutreachTemplate(
                    approach="Curiosity opener", channel="linkedin",
                    body_en="Hi Lena, saw you use Stripe...",
                    body_de="Hallo Lena, ich habe gesehen...",
                ),
                OutreachTemplate(
                    approach="Social proof", channel="linkedin",
                    body_en="Hi Lena, a few teams like yours...",
                    body_de="Hallo Lena, einige Teams wie Ihres...",
                ),
            ]
        )

        async def fake_draft_fn(**kwargs):
            return fake_draft

        import app.routers.admin as admin_mod
        monkeypatch.setattr(admin_mod._outreach_drafter, "draft", fake_draft_fn)

        r = client.post(
            "/admin/outreach",
            data={"company": "Acme GmbH", "founder": "Lena Fischer", "vendor1": "Stripe", "vendor2": "AWS"},
        )
        assert r.status_code == 200
        assert "Direct compliance gap" in r.text
        assert "Hi Lena, ..." in r.text
        assert "Hallo Lena, ..." in r.text

    def test_a_drafting_failure_shows_an_error_not_a_500(self, db_engine, admin_tenant, monkeypatch):
        client = next(_client(db_engine, monkeypatch))
        client.cookies.set("session", _make_session_token(str(admin_tenant.id)))

        async def fake_draft_fn(**kwargs):
            raise RuntimeError("boom")

        import app.routers.admin as admin_mod
        monkeypatch.setattr(admin_mod._outreach_drafter, "draft", fake_draft_fn)

        r = client.post(
            "/admin/outreach",
            data={"company": "Acme", "founder": "Lena", "vendor1": "Stripe", "vendor2": "AWS"},
        )
        assert r.status_code == 200
        assert "Draft failed" in r.text
