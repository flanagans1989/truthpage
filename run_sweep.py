"""
Manuel sweep tetikleyici — 5 dakikalık cron'u beklemeden hemen çalıştır.

Kullanım:
    uv run python run_sweep.py
"""
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

from sqlalchemy import func, select, text

from app.db.models.change_event import ChangeEvent, ChangeStatus
from app.db.models.subprocessor import Subprocessor
from app.db.models.tenant import Tenant
from app.db.session import AsyncSessionLocal
from app.scheduler.jobs import _BILLABLE_STATUSES, sweep_due_subprocessors
from app.db.models.mixins import utc_now


async def _pre_check() -> None:
    """Sweep öncesi scope'taki subprocessor'ları listele."""
    now = utc_now()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subprocessor, Tenant.subscription_status)
            .join(Subprocessor.tenant)
            .where(Subprocessor.monitoring_enabled == True)  # noqa: E712
        )
        rows = result.all()

    if not rows:
        print("  [!] Veritabanında aktif subprocessor yok — dashboard'dan ekle.")
        return

    print(f"  {'Ad':<30} {'Status':<12} {'next_check_at':<30} {'Scope'}")
    print("  " + "-" * 85)
    for sp, status in rows:
        due = (sp.next_check_at is None) or (sp.next_check_at <= now)
        billable = status in _BILLABLE_STATUSES
        scope = "KAPSAM ICINDE" if (due and billable) else (
            "bekliyor (due degil)" if not due else "faturasiz tenant"
        )
        nca = sp.next_check_at.strftime("%H:%M:%S") if sp.next_check_at else "NULL (ilk tarama)"
        print(f"  {sp.name:<30} {status:<12} {nca:<30} {scope}")


async def _post_check() -> None:
    """Sweep sonrası son 5 ChangeEvent'i göster."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ChangeEvent, Subprocessor.name)
            .join(ChangeEvent.subprocessor)
            .order_by(ChangeEvent.created_at.desc())
            .limit(5)
        )
        rows = result.all()

    if not rows:
        print("  Henüz hiç ChangeEvent yok.")
        return

    print(f"  {'Subprocessor':<30} {'Status':<18} {'Sınıf':<12} {'Conf':<6} {'Zaman'}")
    print("  " + "-" * 90)
    for event, sp_name in rows:
        t = event.created_at.strftime("%H:%M:%S") if event.created_at else "-"
        print(
            f"  {sp_name:<30} {event.status:<18} "
            f"{(event.llm_classification or '-'):<12} "
            f"{(event.llm_confidence or 0):<6.2f} {t}"
        )


async def main() -> None:
    print("\n=== Sweep Öncesi Durum ===")
    await _pre_check()

    print("\n=== Manuel Sweep Başlatıldı ===\n")
    await sweep_due_subprocessors(AsyncSessionLocal)

    print("\n=== Son 5 ChangeEvent ===")
    await _post_check()
    print("\n=== Tamamlandı — Onay kuyruğu: http://localhost:8000/dashboard/queue ===\n")


asyncio.run(main())
