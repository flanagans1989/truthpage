"""app/db/models/objection.py — a manually-recorded objection always
carries who entered it (recorded_by_email, the authenticated tenant
identity) separately from who objected (objector_name, free text)."""
import pytest

from app.db.models.change_event import ChangeEvent
from app.db.models.mixins import utc_now
from app.db.models.objection import Objection
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant


class TestObjectionRecording:
    @pytest.mark.asyncio
    async def test_objection_persists_objector_and_recorder_separately(self, session_factory):
        async with session_factory() as session:
            tenant = Tenant(name="Acme", slug="acme", email="owner@acme.com", subscription_status="free")
            session.add(tenant)
            await session.flush()
            sp = Subprocessor(tenant_id=tenant.id, name="Vendor", monitored_url="https://vendor.example.com")
            session.add(sp)
            await session.flush()
            event = ChangeEvent(subprocessor_id=sp.id, old_hash="a" * 64, new_hash="b" * 64, raw_diff="d")
            session.add(event)
            await session.flush()

            objection = Objection(
                change_event_id=event.id,
                objector_name="Jane Customer",
                objected_at=utc_now(),
                note="Called in to object.",
                recorded_by_email="owner@acme.com",
            )
            session.add(objection)
            await session.commit()
            objection_id = objection.id

        async with session_factory() as session:
            reloaded = await session.get(Objection, objection_id)
            assert reloaded.objector_name == "Jane Customer"
            assert reloaded.recorded_by_email == "owner@acme.com"
            assert reloaded.created_at is not None  # when it was entered into TrustPages
