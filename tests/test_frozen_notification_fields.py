"""PR 4's KURAL 0: reviewed_by_name/email/at, review_action,
notice_frozen_*, recipient_count, window_days/window_closes_at never
change once set — app/db/models/change_event.py's validates() guard,
tested the same way PR 3 tests BackdatedTimestampError as a hard trip-wire
rather than only documentation.
"""
import pytest

from app.db.models.change_event import ChangeEvent, FrozenNotificationFieldError
from app.db.models.mixins import utc_now
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant


async def _make_event(session_factory, **overrides) -> ChangeEvent:
    async with session_factory() as session:
        tenant = Tenant(name="Acme", slug="acme", email="owner@acme.com", subscription_status="free")
        session.add(tenant)
        await session.flush()
        sp = Subprocessor(tenant_id=tenant.id, name="Vendor", monitored_url="https://vendor.example.com")
        session.add(sp)
        await session.flush()
        defaults = dict(subprocessor_id=sp.id, old_hash="a" * 64, new_hash="b" * 64, raw_diff="d")
        defaults.update(overrides)
        event = ChangeEvent(**defaults)
        session.add(event)
        await session.commit()
        await session.refresh(event)
        return event


class TestFrozenFieldTripWire:
    @pytest.mark.asyncio
    async def test_reviewed_by_name_cannot_be_changed_once_set(self, session_factory):
        event = await _make_event(session_factory, reviewed_by_name="Jane")
        with pytest.raises(FrozenNotificationFieldError):
            event.reviewed_by_name = "Someone Else"

    @pytest.mark.asyncio
    async def test_review_action_cannot_be_changed_once_set(self, session_factory):
        event = await _make_event(session_factory, review_action="auto_published_cosmetic")
        with pytest.raises(FrozenNotificationFieldError):
            event.review_action = "notice_released_by_reviewer"

    @pytest.mark.asyncio
    async def test_notice_frozen_body_cannot_be_changed_once_set(self, session_factory):
        event = await _make_event(session_factory, notice_frozen_body="Original text")
        with pytest.raises(FrozenNotificationFieldError):
            event.notice_frozen_body = "Rewritten text"

    @pytest.mark.asyncio
    async def test_recipient_count_and_window_days_cannot_be_changed_once_set(self, session_factory):
        event = await _make_event(session_factory, recipient_count=3, window_days=30)
        with pytest.raises(FrozenNotificationFieldError):
            event.recipient_count = 5
        with pytest.raises(FrozenNotificationFieldError):
            event.window_days = 14

    @pytest.mark.asyncio
    async def test_window_closes_at_cannot_be_changed_once_set(self, session_factory):
        now = utc_now()
        event = await _make_event(session_factory, window_closes_at=now)
        with pytest.raises(FrozenNotificationFieldError):
            event.window_closes_at = utc_now()

    @pytest.mark.asyncio
    async def test_setting_the_same_value_again_is_not_an_error(self, session_factory):
        event = await _make_event(session_factory, reviewed_by_name="Jane")
        event.reviewed_by_name = "Jane"  # idempotent re-set — must not raise

    @pytest.mark.asyncio
    async def test_first_set_from_null_is_allowed(self, session_factory):
        event = await _make_event(session_factory)  # all frozen fields still NULL
        event.reviewed_by_name = "Jane"  # first, legitimate write — must not raise
        assert event.reviewed_by_name == "Jane"

    @pytest.mark.asyncio
    async def test_loading_an_already_set_event_from_the_database_does_not_raise(self, session_factory):
        event = await _make_event(
            session_factory, reviewed_by_name="Jane", recipient_count=2, review_action="notice_released_by_reviewer"
        )
        async with session_factory() as session:
            reloaded = await session.get(ChangeEvent, event.id)
            assert reloaded.reviewed_by_name == "Jane"
            assert reloaded.recipient_count == 2
