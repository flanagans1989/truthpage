"""Cancelling Growth must not retract packs already earned.

The export gate used to read the tenant's CURRENT plan. Since an audit
pack is usually wanted for something that happened months ago, cancelling
took away evidence the customer had already paid to have captured — while
we kept both the record and the dashboard page showing it to them. For a
compliance product sold to legal and security teams, that reads as
hostage-taking.
"""
import pytest
import pytest_asyncio

from app.db.models.change_event import ChangeEvent, ChangeStatus
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant


@pytest_asyncio.fixture
async def downgraded_tenant_with_history(session_factory):
    async with session_factory() as session:
        tenant = Tenant(
            slug="acme",
            name="Acme",
            email="a@example.com",
            subscription_status="free",  # cancelled: no current entitlement
        )
        session.add(tenant)
        await session.flush()
        sp = Subprocessor(
            tenant_id=tenant.id,
            name="Vendor",
            monitored_url="https://vendor.example/subprocessors",
        )
        session.add(sp)
        await session.flush()
        earned = ChangeEvent(
            subprocessor_id=sp.id,
            old_hash="a" * 64,
            new_hash="b" * 64,
            raw_diff="-old\n+new",
            status=ChangeStatus.auto_published.value,
            export_entitled=True,  # captured while they were paying
        )
        later = ChangeEvent(
            subprocessor_id=sp.id,
            old_hash="b" * 64,
            new_hash="c" * 64,
            raw_diff="-new\n+newer",
            status=ChangeStatus.auto_published.value,
            export_entitled=False,  # captured after the downgrade
        )
        session.add_all([earned, later])
        await session.commit()
        return tenant, earned.id, later.id


@pytest.mark.asyncio
async def test_entitlement_is_stamped_on_the_record_not_read_from_the_plan(
    downgraded_tenant_with_history, session_factory
):
    _tenant, earned_id, later_id = downgraded_tenant_with_history
    async with session_factory() as session:
        assert (await session.get(ChangeEvent, earned_id)).export_entitled is True
        assert (await session.get(ChangeEvent, later_id)).export_entitled is False


@pytest.mark.asyncio
async def test_a_downgraded_tenant_has_no_current_entitlement(
    downgraded_tenant_with_history,
):
    tenant, _earned, _later = downgraded_tenant_with_history
    # The premise of the whole test: today's plan says no...
    assert tenant.may_export_evidence is False


@pytest.mark.asyncio
async def test_the_export_gate_is_the_or_of_plan_and_record(
    downgraded_tenant_with_history, session_factory
):
    """...and the pack earned under Growth is still exportable anyway."""
    tenant, earned_id, later_id = downgraded_tenant_with_history
    async with session_factory() as session:
        earned = await session.get(ChangeEvent, earned_id)
        later = await session.get(ChangeEvent, later_id)

        assert (tenant.may_export_evidence or earned.export_entitled) is True
        # A change captured after the downgrade is not retroactively bought.
        assert (tenant.may_export_evidence or later.export_entitled) is False
