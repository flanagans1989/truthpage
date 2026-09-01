"""Plan transitions.

The only transition that happens on its own: a trial that runs out. Rather
than switching the account off, it lands on the permanent free plan with a
few pages still watched — a dead account tells the tenant nothing, and a
trust page that stops updating is worse for their customers than for us.
"""
from collections.abc import Iterable, Sequence
from typing import Any


def free_plan_split(
    subprocessors: Iterable[Any], limit: int
) -> tuple[list[Any], list[Any]]:
    """Split a tenant's pages into (kept, dropped) for the free plan.

    Oldest first: the pages added at the very beginning are the ones the
    tenant chose most deliberately, and keeping the newest would silently
    drop whatever they set up on day one. Rows already switched off by the
    tenant are counted as dropped without touching them, so a tenant who
    curated their own list keeps that choice.
    """
    ordered: Sequence[Any] = sorted(
        subprocessors, key=lambda sp: (sp.created_at, str(sp.id))
    )
    kept: list[Any] = []
    dropped: list[Any] = []
    for sp in ordered:
        if not sp.monitoring_enabled:
            dropped.append(sp)
        elif len(kept) < limit:
            kept.append(sp)
        else:
            dropped.append(sp)
    return kept, dropped
