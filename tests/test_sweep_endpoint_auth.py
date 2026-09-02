"""POST /internal/sweep authentication.

Until 2026-09-02 this endpoint compared its header against JWT_SECRET —
the same key that signs login sessions. Leaking the cron header therefore
also meant being able to forge any user's session, and vice versa. It was
also unmetered, which made a leaked secret a way to burn Neon compute
hours on demand (the failure that took the site down on 2026-08-24).
"""
import app.main as main
from app.core.config import settings


def test_sweep_disabled_when_secret_unset(anon_client, monkeypatch):
    monkeypatch.setattr(settings, "SWEEP_SECRET", "")
    response = anon_client.post("/internal/sweep", headers={"X-Admin-Secret": "anything"})
    assert response.status_code == 503


def test_sweep_rejects_jwt_secret(anon_client, monkeypatch):
    """The old key must no longer open this door."""
    monkeypatch.setattr(settings, "SWEEP_SECRET", "a-separate-sweep-secret")
    response = anon_client.post(
        "/internal/sweep", headers={"X-Admin-Secret": settings.JWT_SECRET}
    )
    assert response.status_code == 403


def test_sweep_accepts_its_own_secret_and_is_rate_limited(anon_client, monkeypatch):
    monkeypatch.setattr(settings, "SWEEP_SECRET", "a-separate-sweep-secret")
    monkeypatch.setattr(main._sweep_limiter, "_max", 2)

    async def _noop(_factory):
        return None

    monkeypatch.setattr(main, "run_sweep_cycle", _noop)

    headers = {"X-Admin-Secret": "a-separate-sweep-secret"}
    assert anon_client.post("/internal/sweep", headers=headers).status_code == 200
    assert anon_client.post("/internal/sweep", headers=headers).status_code == 200
    # Third call inside the window is refused — a leaked secret is not an
    # unmetered compute drain.
    assert anon_client.post("/internal/sweep", headers=headers).status_code == 429
