"""Insert directory candidates from app/core/vendor_seeds.py.

Idempotent: an existing slug is left alone, including its baseline and its
change history. Adding a vendor here does not publish it — the next sweep
fetches the page, and only a page the extractor can actually read a list off
becomes a public page.

    uv run python seed_vendors.py           # insert missing candidates
    uv run python seed_vendors.py --check   # report only, write nothing
"""
import asyncio
import sys

from sqlalchemy import select

from app.core.vendor_seeds import VENDOR_SEEDS
from app.db.models.vendor import Vendor
from app.db.session import AsyncSessionLocal


async def main(dry_run: bool) -> None:
    async with AsyncSessionLocal() as session:
        existing = set(
            (await session.execute(select(Vendor.slug))).scalars().all()
        )
        missing = [s for s in VENDOR_SEEDS if s["slug"] not in existing]

        print(f"{len(existing)} vendor(s) already present, {len(missing)} to add")
        for seed in missing:
            print(f"  + {seed['slug']:<16} {seed['monitored_url']}")

        if dry_run or not missing:
            return

        for seed in missing:
            session.add(Vendor(**seed))
        await session.commit()
        print(f"inserted {len(missing)} vendor(s) — unpublished until their first check")


if __name__ == "__main__":
    asyncio.run(main(dry_run="--check" in sys.argv))
