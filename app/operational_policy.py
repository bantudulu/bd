from __future__ import annotations

from datetime import datetime, timezone

# Boundary for the first production Operational V1 flow.
# Git commit 6f958eb was created at 2026-09-07T06:29:07Z.
OPERATIONAL_V1_CUTOFF_DB = datetime(2026, 9, 7, 6, 29, 7)


def is_pre_operational_v1(created_at: datetime | None) -> bool:
    if created_at is None:
        return True
    value = created_at
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value < OPERATIONAL_V1_CUTOFF_DB


def is_archived_variant_name(name: str | None) -> bool:
    return "arsip" in (name or "").strip().casefold()
