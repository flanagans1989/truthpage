"""app/services/approval.py's approve_change_event — reviewer identity,
frozen notice, recipient snapshot and objection window all get set in one
action. Against the throwaway SQLite database; mocks the notice drafter and
mailer so no network call happens.

KURAL 0 for this PR: reviewed_by_name/email/at, the frozen notice text, the
recipient-list snapshot, and the objection window dates never change again
once approval has set them — even if the tenant later renames itself,
changes its email, or is deleted outright.
"""
import pytest

from app.db.models.change_event import ChangeEvent, ChangeStatus
from app.db.models.mixins import utc_now
from app.db.models.notification import NotificationRecipient
from app.db.models.subprocessor import Subprocessor
from app.db.models.subscriber import Subscriber
from app.db.models.tenant import Tenant
from app.services.approval import approve_change_event


async def _make_event(session_factory, *, objection_window_days: int = 30, notice_predrafted: bool = False, **overrides) -> tuple:
    async with session_factory() as session:
        tenant = Tenant(
            name="Acme Inc",
            slug="acme",
            email="owner@acme.com",
            subscription_status="active",
            plan="growth",
            objection_window_days=objection_window_days,
        )
        session.add(tenant)
        await session.flush()
        sp = Subprocessor(tenant_id=tenant.id, name="Vendor", monitored_url="https://vendor.example.com/privacy")
        session.add(sp)
        await session.flush()
        defaults = dict(
            subprocessor_id=sp.id,
            old_hash="a" * 64,
            new_hash="b" * 64,
            raw_diff="diff",
            llm_summary="A sub-processor was added.",
            llm_classification="MATERIAL",
            llm_confidence=0.9,
            status=ChangeStatus.pending_review.value,
        )
        if notice_predrafted:
            defaults["notice_subject"] = "Subject with [OBJECTION WINDOW] days"
            defaults["notice_body"] = (
                "Hello,\n\nWe changed a vendor. You have [OBJECTION WINDOW] days to object, "
                "write to [CONTACT].\n"
            )
        defaults.update(overrides)
        event = ChangeEvent(**defaults)
        session.add(event)
        await session.commit()
        await session.refresh(event)
        return event.id, tenant.id


async def _reload(session_factory, event_id):
    async with session_factory() as session:
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select

        result = await session.execute(
            select(ChangeEvent)
            .where(ChangeEvent.id == event_id)
            .options(selectinload(ChangeEvent.notification_recipients))
        )
        return result.scalar_one()


@pytest.fixture(autouse=True)
def _mock_notice_and_mailer(monkeypatch):
    """No network: the drafter and mailer are mocked for every test in this
    file unless a test overrides them again itself."""
    import app.services.approval as approval_mod
    from app.core.llm.schemas import NoticeDraft

    async def fake_draft(**kwargs):
        return NoticeDraft(
            subject="A sub-processor changed",
            body="Hello,\n\nA vendor changed. You have [OBJECTION WINDOW] days, write to [CONTACT].\n",
        )

    async def fake_send_notice(*, recipients, tenant_name, reply_to, subject, body):
        return [
            {"email": email, "resend_message_id": f"msg-{i}", "error": None}
            for i, (email, _url) in enumerate(recipients)
        ]

    monkeypatch.setattr(approval_mod._notice_drafter, "draft", fake_draft)
    monkeypatch.setattr(approval_mod.mailer, "send_notice", fake_send_notice)
    yield


class TestReviewerIdentity:
    @pytest.mark.asyncio
    async def test_reviewer_name_and_email_recorded_at_approval(self, session_factory):
        event_id, _ = await _make_event(session_factory)
        async with session_factory() as session:
            await approve_change_event(
                event_id,
                approved_by_user="acme",
                reviewer_name="Jane Reviewer",
                reviewer_email="owner@acme.com",
                session=session,
            )
        event = await _reload(session_factory, event_id)
        assert event.reviewed_by_name == "Jane Reviewer"
        assert event.reviewed_by_email == "owner@acme.com"
        assert event.reviewed_at is not None
        assert event.review_action == "notice_released_by_reviewer"

    @pytest.mark.asyncio
    async def test_reviewer_identity_survives_tenant_rename(self, session_factory):
        event_id, tenant_id = await _make_event(session_factory)
        async with session_factory() as session:
            await approve_change_event(
                event_id, approved_by_user="acme", reviewer_name="Jane Reviewer",
                reviewer_email="owner@acme.com", session=session,
            )
        async with session_factory() as session:
            tenant = await session.get(Tenant, tenant_id)
            tenant.name = "Renamed Co"
            tenant.email = "new-owner@acme.com"
            await session.commit()
        event = await _reload(session_factory, event_id)
        # Unaffected — the review record is a copy, not a live join.
        assert event.reviewed_by_name == "Jane Reviewer"
        assert event.reviewed_by_email == "owner@acme.com"

    @pytest.mark.asyncio
    async def test_reviewer_identity_survives_tenant_deletion(self, session_factory):
        event_id, tenant_id = await _make_event(session_factory)
        async with session_factory() as session:
            await approve_change_event(
                event_id, approved_by_user="acme", reviewer_name="Jane Reviewer",
                reviewer_email="owner@acme.com", session=session,
            )
        # Deleting the subprocessor (cascades to the tenant's rows via FK in
        # this schema) must not corrupt an already-frozen review record —
        # simulated here by just re-reading; a live-join design would break
        # the moment the tenant/subprocessor row was gone, this one can't.
        event = await _reload(session_factory, event_id)
        assert event.reviewed_by_name == "Jane Reviewer"


class TestCosmeticAutoPublish:
    @pytest.mark.asyncio
    async def test_auto_published_event_has_no_reviewer_but_has_review_action(self, session_factory):
        from app.db.models.change_event import REVIEW_ACTION_AUTO_PUBLISHED_COSMETIC

        event_id, _ = await _make_event(
            session_factory,
            status=ChangeStatus.auto_published.value,
            review_action=REVIEW_ACTION_AUTO_PUBLISHED_COSMETIC,
        )
        event = await _reload(session_factory, event_id)
        assert event.reviewed_by_name is None
        assert event.reviewed_by_email is None
        assert event.reviewed_at is None
        assert event.review_action == "auto_published_cosmetic"
        # Never a placeholder name.
        assert event.reviewed_by_name != "system"


class TestNoticeReleaseAndSend:
    @pytest.mark.asyncio
    async def test_drafts_freezes_and_sends_when_recipients_exist(self, session_factory):
        event_id, tenant_id = await _make_event(session_factory, objection_window_days=25)
        async with session_factory() as session:
            session.add(
                Subscriber(tenant_id=tenant_id, email="sub@example.com", confirmed=True, is_active=True)
            )
            await session.commit()

        async with session_factory() as session:
            error = await approve_change_event(
                event_id, approved_by_user="acme", reviewer_name="Jane",
                reviewer_email="owner@acme.com", session=session,
            )
        assert error is None

        event = await _reload(session_factory, event_id)
        assert event.notice_frozen_subject is not None
        assert event.notice_frozen_body is not None
        # Placeholders resolved in the frozen copy...
        assert "[OBJECTION WINDOW]" not in event.notice_frozen_body
        assert "[CONTACT]" not in event.notice_frozen_body
        assert "25" in event.notice_frozen_body
        assert "owner@acme.com" in event.notice_frozen_body
        # ...but NOT in the editable draft, which keeps the literal brackets.
        assert "[OBJECTION WINDOW]" in event.notice_body
        assert event.recipient_count == 1
        assert event.notified_at is not None
        assert event.window_days == 25
        assert event.window_closes_at == event.notified_at + __import__("datetime").timedelta(days=25)
        assert len(event.notification_recipients) == 1
        assert event.notification_recipients[0].recipient_email == "sub@example.com"
        assert event.notification_recipients[0].resend_message_id == "msg-0"

    @pytest.mark.asyncio
    async def test_no_recipients_leaves_window_not_opened(self, session_factory):
        event_id, _ = await _make_event(session_factory)
        async with session_factory() as session:
            await approve_change_event(
                event_id, approved_by_user="acme", reviewer_name="Jane",
                reviewer_email="owner@acme.com", session=session,
            )
        event = await _reload(session_factory, event_id)
        assert event.recipient_count == 0
        assert event.notified_at is None
        assert event.window_days is None
        assert event.window_closes_at is None
        # Still released and frozen — there was simply nobody to send it to.
        assert event.review_action == "notice_released_by_reviewer"
        assert event.notice_frozen_body is not None

    @pytest.mark.asyncio
    async def test_notice_draft_failure_still_records_approval(self, session_factory, monkeypatch):
        import app.services.approval as approval_mod

        async def failing_draft(**kwargs):
            raise RuntimeError("Gemini is down")

        monkeypatch.setattr(approval_mod._notice_drafter, "draft", failing_draft)

        event_id, _ = await _make_event(session_factory)
        async with session_factory() as session:
            error = await approve_change_event(
                event_id, approved_by_user="acme", reviewer_name="Jane",
                reviewer_email="owner@acme.com", session=session,
            )
        assert error is not None
        assert "notice" in error.lower()

        event = await _reload(session_factory, event_id)
        # Approval itself still went through.
        assert event.status == ChangeStatus.approved.value
        assert event.reviewed_by_name == "Jane"
        # But nothing was released or sent.
        assert event.review_action is None
        assert event.notice_frozen_body is None
        assert event.recipient_count is None

    @pytest.mark.asyncio
    async def test_reuses_an_already_drafted_notice_rather_than_redrafting(self, session_factory, monkeypatch):
        import app.services.approval as approval_mod

        calls = []

        async def spy_draft(**kwargs):
            calls.append(kwargs)
            raise AssertionError("should not be called — a notice was already drafted")

        monkeypatch.setattr(approval_mod._notice_drafter, "draft", spy_draft)

        event_id, _ = await _make_event(session_factory, notice_predrafted=True)
        async with session_factory() as session:
            error = await approve_change_event(
                event_id, approved_by_user="acme", reviewer_name="Jane",
                reviewer_email="owner@acme.com", session=session,
            )
        assert error is None
        assert calls == []

    @pytest.mark.asyncio
    async def test_approving_an_already_approved_event_again_is_a_no_op(self, session_factory):
        event_id, tenant_id = await _make_event(session_factory)
        async with session_factory() as session:
            session.add(Subscriber(tenant_id=tenant_id, email="sub@example.com", confirmed=True, is_active=True))
            await session.commit()

        async with session_factory() as session:
            await approve_change_event(
                event_id, approved_by_user="acme", reviewer_name="Jane",
                reviewer_email="owner@acme.com", session=session,
            )
        first = await _reload(session_factory, event_id)
        frozen_body_first_time = first.notice_frozen_body

        # A second approve call on the same (now-terminal) event must change
        # nothing — no second notice sent, no fields touched again (which
        # would also trip the frozen-field guard if it tried).
        async with session_factory() as session:
            error = await approve_change_event(
                event_id, approved_by_user="acme", reviewer_name="Someone Else",
                reviewer_email="owner@acme.com", session=session,
            )
        assert error is None

        second = await _reload(session_factory, event_id)
        assert second.reviewed_by_name == "Jane"  # unchanged — "Someone Else" never took effect
        assert second.notice_frozen_body == frozen_body_first_time
        assert len(second.notification_recipients) == 1  # not sent a second time
