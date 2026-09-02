"""The dead-man's switch.

Every other alarm in this system is produced BY a sweep tick. If the sweep
stops, nothing errors and nothing goes stale in code — the silence is
total, and /healthz stays green because the process and the database are
both fine. These tests pin the one signal that can tell the difference.
"""
from datetime import timedelta

import pytest

from app.core.config import settings
from app.db.models.mixins import utc_now
from app.db.models.system_state import SWEEP_LAST_COMPLETED_AT, SWEEP_LAST_ERROR
from app.services.system_state import get_state, record_state, set_state


@pytest.mark.asyncio
async def test_record_state_upserts_rather_than_duplicating(session_factory):
    await record_state(session_factory, SWEEP_LAST_COMPLETED_AT, value="1.0s")
    await record_state(session_factory, SWEEP_LAST_COMPLETED_AT, value="2.0s")

    async with session_factory() as session:
        row = await get_state(session, SWEEP_LAST_COMPLETED_AT)
        assert row is not None
        assert row.value == "2.0s"


@pytest.mark.asyncio
async def test_record_state_never_raises(monkeypatch, session_factory):
    """A broken heartbeat must not abort the cycle it is describing."""

    class _Boom:
        def __call__(self, *_a, **_k):
            raise RuntimeError("database is on fire")

    monkeypatch.setattr("app.services.system_state.set_state", _Boom())
    # No exception escapes.
    await record_state(session_factory, SWEEP_LAST_COMPLETED_AT)


import httpx
import pytest_asyncio


@pytest_asyncio.fixture
async def probe_client(session_factory):
    """ASGI client driven from the test's own event loop.

    TestClient runs the app in a separate thread with its own loop, and the
    in-memory SQLite connection these tests seed cannot be used from there.
    """
    from app.db.session import get_db_session
    from app.main import app

    async def _override():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


async def _seed(session_factory, **states):
    async with session_factory() as session:
        for key, kwargs in states.items():
            await set_state(session, key, **kwargs)
        await session.commit()


@pytest.mark.asyncio
async def test_monitoring_probe_ok_when_sweep_is_recent(probe_client, session_factory):
    await _seed(session_factory, **{SWEEP_LAST_COMPLETED_AT: {"value": "3.0s"}})

    response = await probe_client.get("/healthz/monitoring")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["reason"] is None
    assert body["sweep_age_seconds"] is not None


@pytest.mark.asyncio
async def test_monitoring_probe_degrades_when_sweep_is_stale(probe_client, session_factory):
    stale = utc_now() - timedelta(hours=settings.SWEEP_MAX_AGE_HOURS + 5)
    await _seed(session_factory, **{SWEEP_LAST_COMPLETED_AT: {"occurred_at": stale}})

    response = await probe_client.get("/healthz/monitoring")
    # 503 is the whole point: an external uptime monitor has to see red.
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert "last sweep completed" in body["reason"]


@pytest.mark.asyncio
async def test_monitoring_probe_surfaces_last_sweep_error(probe_client, session_factory):
    await _seed(
        session_factory,
        **{
            SWEEP_LAST_COMPLETED_AT: {"value": "1.0s"},
            SWEEP_LAST_ERROR: {"value": "RuntimeError('boom')"},
        },
    )

    response = await probe_client.get("/healthz/monitoring")
    assert "boom" in response.json()["last_sweep_error"]


@pytest.mark.asyncio
async def test_never_completed_sweep_is_ok_during_boot_grace_then_degrades(
    probe_client, monkeypatch
):
    """A fresh deploy has no completed cycle yet and must not start red —
    but the grace window has to actually expire, or the probe is decorative."""
    import app.main as main

    assert (await probe_client.get("/healthz/monitoring")).status_code == 200

    monkeypatch.setattr(main, "_BOOT_AT", utc_now() - timedelta(hours=2))
    response = await probe_client.get("/healthz/monitoring")
    assert response.status_code == 503
    assert response.json()["reason"] == "no sweep cycle has completed"


def test_render_health_check_does_not_point_at_the_monitoring_probe():
    """Render restarts or fails a deploy on a non-200 from healthCheckPath.

    /healthz/monitoring returns 503 by design whenever the sweep is stale,
    so pointing Render at it would turn "monitoring fell behind" into
    "tear the service down", which is the opposite of the intent.
    """
    import pathlib

    render_yaml = (
        pathlib.Path(__file__).resolve().parents[1] / "render.yaml"
    ).read_text(encoding="utf-8")
    assert "healthCheckPath: /healthz\n" in render_yaml
    assert "healthCheckPath: /healthz/monitoring" not in render_yaml
