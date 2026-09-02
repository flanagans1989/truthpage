"""app/services/approval.py — approve_change_event (records the decision
only) and release_notice (the separate, explicit "send" action). Against
the throwaway SQLite database; mocks the notice drafter and mailer so no
network call happens.

KURAL 0 for this PR: reviewed_by_name/email/at, the frozen notice text,
the recipient-list snapshot, and the objection window dates never change
again once release_notice has set them — even if the tenant later renames
itself, changes its email, or is deleted outright. Separately: a notice
can never be sent without the caller having first loaded the exact
current draft (notice_preview_token must match) — approving a change is
not itself an attestation that anyone read the final notice text.
"""
import pytest

from app.core.llm.notice import notice_preview_token
from app.db.models.change_event import ChangeEvent, ChangeStatus
from app.db.models.notification import NotificationRecipient
from app.db.models.subprocessor import Subprocessor
from app.db.models.subscriber import Subscriber
from app.db.models.tenant import Tenant
from app.services.approval import approve_change_event, release_notice


async def _make_event(
    session_factory, *, objection_window_days: int = 30, notice_predrafted: bool = False,
    privacy_contact_email: str | None = None, **overrides,
) -> tuple:
    async with session_factory() as session:
        tenant = Tenant(
            name="Acme Inc",
            slug="acme",
            email="owner@acme.com",
            subscription_status="active",
            plan="growth",
            objection_window_days=objection_window_days,
            privacy_contact_email=privacy_contact_email,
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


async def _approve(session_factory, event_id):
    async with session_factory() as session:
        await approve_change_event(event_id, approved_by_user="acme", session=session)


async def _reload(session_factory, event_id):
    async with session_factory() as session:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

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


class TestApproveIsRecordOnly:
    @pytest.mark.asyncio
    async def test_approving_does_not_draft_freeze_or_send_anything(self, session_factory, monkeypatch):
        import app.services.approval as approval_mod

        async def fail_if_called(**kwargs):
            raise AssertionError("approve_change_event must never draft a notice")

        monkeypatch.setattr(approval_mod._notice_drafter, "draft", fail_if_called)

        async def fail_if_sent(**kwargs):
            raise AssertionError("approve_change_event must never send anything")

        monkeypatch.setattr(approval_mod.mailer, "send_notice", fail_if_sent)

        event_id, _ = await _make_event(session_factory)
        await _approve(session_factory, event_id)

        event = await _reload(session_factory, event_id)
        assert event.status == ChangeStatus.approved.value
        assert event.reviewed_by_name is None
        assert event.review_action is None
        assert event.notice_frozen_body is None
        assert event.recipient_count is None


class TestReleaseRequiresApproval:
    @pytest.mark.asyncio
    async def test_cannot_release_a_not_yet_approved_event(self, session_factory):
        event_id, _ = await _make_event(session_factory, notice_predrafted=True)
        async with session_factory() as session:
            error = await release_notice(
                event_id, reviewer_name="Jane", reviewer_email="owner@acme.com",
                notice_body_preview_token="irrelevant", session=session,
            )
        assert error is not None
        assert "approve" in error.lower()


class TestReleaseRequiresSeeingTheCurrentText:
    @pytest.mark.asyncio
    async def test_wrong_preview_token_is_refused_and_sends_nothing(self, session_factory, monkeypatch):
        import app.services.approval as approval_mod

        async def fail_if_sent(**kwargs):
            raise AssertionError("must never send when the preview token doesn't match")

        monkeypatch.setattr(approval_mod.mailer, "send_notice", fail_if_sent)

        event_id, tenant_id = await _make_event(session_factory, notice_predrafted=True)
        await _approve(session_factory, event_id)

        async with session_factory() as session:
            error = await release_notice(
                event_id, reviewer_name="Jane", reviewer_email="owner@acme.com",
                notice_body_preview_token="stale-or-forged-token", session=session,
            )
        assert error is not None
        assert "changed" in error.lower() or "reload" in error.lower()

        event = await _reload(session_factory, event_id)
        assert event.review_action is None
        assert event.notice_frozen_body is None

    @pytest.mark.asyncio
    async def test_correct_preview_token_succeeds(self, session_factory):
        event_id, tenant_id = await _make_event(session_factory, notice_predrafted=True)
        await _approve(session_factory, event_id)

        event = await _reload(session_factory, event_id)
        token = notice_preview_token(event.notice_body)

        async with session_factory() as session:
            error = await release_notice(
                event_id, reviewer_name="Jane", reviewer_email="owner@acme.com",
                notice_body_preview_token=token, session=session,
            )
        assert error is None

    @pytest.mark.asyncio
    async def test_cannot_release_without_a_draft_at_all(self, session_factory):
        event_id, _ = await _make_event(session_factory)  # no notice_predrafted
        await _approve(session_factory, event_id)
        async with session_factory() as session:
            error = await release_notice(
                event_id, reviewer_name="Jane", reviewer_email="owner@acme.com",
                notice_body_preview_token="anything", session=session,
            )
        assert error is not None
        assert "draft" in error.lower()

    @pytest.mark.asyncio
    async def test_cannot_release_the_same_notice_twice(self, session_factory):
        event_id, _ = await _make_event(session_factory, notice_predrafted=True)
        await _approve(session_factory, event_id)
        event = await _reload(session_factory, event_id)
        token = notice_preview_token(event.notice_body)

        async with session_factory() as session:
            first_error = await release_notice(
                event_id, reviewer_name="Jane", reviewer_email="owner@acme.com",
                notice_body_preview_token=token, session=session,
            )
        assert first_error is None

        async with session_factory() as session:
            second_error = await release_notice(
                event_id, reviewer_name="Someone Else", reviewer_email="owner@acme.com",
                notice_body_preview_token=token, session=session,
            )
        assert second_error is not None
        assert "already" in second_error.lower()

        event = await _reload(session_factory, event_id)
        assert event.reviewed_by_name == "Jane"  # "Someone Else" never took effect


class TestReviewerIdentity:
    @pytest.mark.asyncio
    async def test_reviewer_name_and_email_recorded_at_release(self, session_factory):
        event_id, _ = await _make_event(session_factory, notice_predrafted=True)
        await _approve(session_factory, event_id)
        event = await _reload(session_factory, event_id)
        token = notice_preview_token(event.notice_body)

        async with session_factory() as session:
            await release_notice(
                event_id, reviewer_name="Jane Reviewer", reviewer_email="owner@acme.com",
                notice_body_preview_token=token, session=session,
            )
        event = await _reload(session_factory, event_id)
        assert event.reviewed_by_name == "Jane Reviewer"
        assert event.reviewed_by_email == "owner@acme.com"
        assert event.reviewed_at is not None
        assert event.review_action == "notice_released_by_reviewer"

    @pytest.mark.asyncio
    async def test_reviewer_identity_survives_tenant_rename(self, session_factory):
        event_id, tenant_id = await _make_event(session_factory, notice_predrafted=True)
        await _approve(session_factory, event_id)
        event = await _reload(session_factory, event_id)
        token = notice_preview_token(event.notice_body)
        async with session_factory() as session:
            await release_notice(
                event_id, reviewer_name="Jane Reviewer", reviewer_email="owner@acme.com",
                notice_body_preview_token=token, session=session,
            )

        async with session_factory() as session:
            tenant = await session.get(Tenant, tenant_id)
            tenant.name = "Renamed Co"
            tenant.email = "new-owner@acme.com"
            await session.commit()

        event = await _reload(session_factory, event_id)
        assert event.reviewed_by_name == "Jane Reviewer"
        assert event.reviewed_by_email == "owner@acme.com"


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
        assert event.review_action == "auto_published_cosmetic"
        assert event.reviewed_by_name != "system"


class TestReleaseNoticeSend:
    @pytest.mark.asyncio
    async def test_freezes_placeholders_and_sends_when_recipients_exist(self, session_factory):
        event_id, tenant_id = await _make_event(session_factory, objection_window_days=25, notice_predrafted=True)
        await _approve(session_factory, event_id)
        async with session_factory() as session:
            session.add(
                Subscriber(tenant_id=tenant_id, email="sub@example.com", confirmed=True, is_active=True)
            )
            await session.commit()

        event = await _reload(session_factory, event_id)
        token = notice_preview_token(event.notice_body)
        async with session_factory() as session:
            error = await release_notice(
                event_id, reviewer_name="Jane", reviewer_email="owner@acme.com",
                notice_body_preview_token=token, session=session,
            )
        assert error is None

        event = await _reload(session_factory, event_id)
        assert "[OBJECTION WINDOW]" not in event.notice_frozen_body
        assert "[CONTACT]" not in event.notice_frozen_body
        assert "25" in event.notice_frozen_body
        assert "owner@acme.com" in event.notice_frozen_body  # falls back to account email
        assert "[OBJECTION WINDOW]" in event.notice_body  # editable draft keeps literal brackets
        assert event.recipient_count == 1
        assert event.notified_at is not None
        assert event.window_days == 25
        import datetime as _dt
        assert event.window_closes_at == event.notified_at + _dt.timedelta(days=25)
        assert len(event.notification_recipients) == 1
        assert event.notification_recipients[0].recipient_email == "sub@example.com"

    @pytest.mark.asyncio
    async def test_uses_dedicated_privacy_contact_email_when_set(self, session_factory):
        event_id, tenant_id = await _make_event(
            session_factory, notice_predrafted=True, privacy_contact_email="privacy@acme.com",
        )
        await _approve(session_factory, event_id)
        event = await _reload(session_factory, event_id)
        token = notice_preview_token(event.notice_body)
        async with session_factory() as session:
            await release_notice(
                event_id, reviewer_name="Jane", reviewer_email="owner@acme.com",
                notice_body_preview_token=token, session=session,
            )
        event = await _reload(session_factory, event_id)
        assert "privacy@acme.com" in event.notice_frozen_body
        assert "owner@acme.com" not in event.notice_frozen_body

    @pytest.mark.asyncio
    async def test_no_recipients_leaves_window_not_opened(self, session_factory):
        event_id, _ = await _make_event(session_factory, notice_predrafted=True)
        await _approve(session_factory, event_id)
        event = await _reload(session_factory, event_id)
        token = notice_preview_token(event.notice_body)
        async with session_factory() as session:
            await release_notice(
                event_id, reviewer_name="Jane", reviewer_email="owner@acme.com",
                notice_body_preview_token=token, session=session,
            )
        event = await _reload(session_factory, event_id)
        assert event.recipient_count == 0
        assert event.notified_at is None
        assert event.window_days is None
        assert event.window_closes_at is None
        assert event.review_action == "notice_released_by_reviewer"
        assert event.notice_frozen_body is not None
