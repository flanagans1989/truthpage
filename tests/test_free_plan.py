from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.plans import free_plan_split

BASE = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _sp(n: int, enabled: bool = True):
    return SimpleNamespace(id=f"sp-{n}", created_at=BASE + timedelta(days=n), monitoring_enabled=enabled)


class TestFreePlanSplit:
    def test_keeps_the_oldest_pages(self):
        pages = [_sp(3), _sp(1), _sp(2), _sp(4)]
        kept, dropped = free_plan_split(pages, limit=2)
        assert [p.id for p in kept] == ["sp-1", "sp-2"]
        assert [p.id for p in dropped] == ["sp-3", "sp-4"]

    def test_under_the_limit_nothing_is_dropped(self):
        kept, dropped = free_plan_split([_sp(1), _sp(2)], limit=3)
        assert len(kept) == 2
        assert dropped == []

    def test_empty_tenant(self):
        assert free_plan_split([], limit=3) == ([], [])

    def test_pages_the_tenant_switched_off_do_not_consume_the_allowance(self):
        # sp-1 is the oldest but already off; the allowance goes to the two
        # oldest pages the tenant is actually watching.
        pages = [_sp(1, enabled=False), _sp(2), _sp(3), _sp(4)]
        kept, dropped = free_plan_split(pages, limit=2)
        assert [p.id for p in kept] == ["sp-2", "sp-3"]
        assert [p.id for p in dropped] == ["sp-1", "sp-4"]

    def test_split_is_total(self):
        pages = [_sp(n) for n in range(6)]
        kept, dropped = free_plan_split(pages, limit=3)
        assert len(kept) + len(dropped) == len(pages)

    def test_zero_limit_drops_everything(self):
        kept, dropped = free_plan_split([_sp(1), _sp(2)], limit=0)
        assert kept == []
        assert len(dropped) == 2

    def test_same_timestamp_falls_back_to_a_stable_order(self):
        a = SimpleNamespace(id="sp-b", created_at=BASE, monitoring_enabled=True)
        b = SimpleNamespace(id="sp-a", created_at=BASE, monitoring_enabled=True)
        kept, _ = free_plan_split([a, b], limit=1)
        assert [p.id for p in kept] == ["sp-a"]


class TestTenantLimit:
    def test_free_and_paid_caps_differ(self):
        from app.core.config import settings
        from app.db.models.tenant import Tenant

        free = Tenant(name="x", slug="x", subscription_status="free")
        paid = Tenant(name="y", slug="y", subscription_status="active")
        assert free.is_free_plan is True
        assert paid.is_free_plan is False
        assert free.subprocessor_limit == settings.FREE_TIER_MAX_SUBPROCESSORS
        assert paid.subprocessor_limit == settings.MAX_SUBPROCESSORS_PER_TENANT

    def test_trialing_tenant_gets_the_paid_cap(self):
        from app.core.config import settings
        from app.db.models.tenant import Tenant

        assert Tenant(name="z", slug="z", subscription_status="trialing").subprocessor_limit == (
            settings.MAX_SUBPROCESSORS_PER_TENANT
        )

    def test_free_is_an_allowed_status(self):
        from app.db.models.tenant import MONITORED_STATUSES, SUBSCRIPTION_STATUSES

        assert "free" in SUBSCRIPTION_STATUSES
        assert "free" in MONITORED_STATUSES
