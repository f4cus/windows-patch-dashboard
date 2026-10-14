"""Dependency-free gate for scheduled/manual refresh jobs; no Microsoft access."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from windows_patch_collector.calendar import ART, refresh_times, resolve_report_month_at

# UTC candidates mirror pages.yml. Weekdays use datetime's Monday=0 convention.
CRON_SLOTS: dict[str, tuple[int, tuple[int, ...], tuple[int, ...]]] = {
    "0 18 * * *": (0, (18,), tuple(range(7))),
    "15 17-23 * * 2": (15, tuple(range(17, 24)), (1,)),
    "15 0,1 * * 3": (15, (0, 1), (2,)),
    "0 12,14,16,20,22 * * 3": (0, (12, 14, 16, 20, 22), (2,)),
    "0 12,16,20 * * 4": (0, (12, 16, 20), (3,)),
    "0 0 * * 4,5": (0, (0,), (3, 4)),
    "0 12 * * 5": (0, (12,), (4,)),
}
MAX_DELAY = timedelta(hours=6)


@dataclass(frozen=True, slots=True)
class RefreshPlan:
    enabled: bool
    month: str | None = None
    slot: datetime | None = None


def plan_refresh(
    event: str,
    created_at: datetime,
    *,
    schedule: str = "",
    manual_month: str | None = None,
    now: datetime | None = None,
) -> RefreshPlan:
    """Anchor queued jobs to run creation, allow bounded delays, never replay gaps."""

    if created_at.tzinfo is None or (now is not None and now.tzinfo is None):
        raise ValueError("An explicit time zone is required")
    if event == "workflow_dispatch":
        return RefreshPlan(True, resolve_report_month_at(now or created_at, manual_month))
    if event != "schedule":
        return RefreshPlan(False)
    minute, hours, weekdays = CRON_SLOTS[schedule]
    created = created_at.astimezone(UTC)
    candidates = (
        datetime.combine(created.date() - timedelta(days=offset), time(hour, minute), UTC)
        for offset in range(8)
        for hour in hours
    )
    slot = max(value for value in candidates if value <= created and value.weekday() in weekdays)
    age = (now or created) - slot
    if age < timedelta(0) or age > MAX_DELAY:
        return RefreshPlan(False)
    local = slot.astimezone(ART)
    if local.time() not in refresh_times(local.date()):
        return RefreshPlan(False)
    return RefreshPlan(True, resolve_report_month_at(slot), slot)


def parse_instant(value: str) -> datetime:
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        raise ValueError("An explicit time zone is required")
    return instant


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True)
    parser.add_argument("--at", type=parse_instant)
    parser.add_argument("--schedule", default="")
    parser.add_argument("--month")
    arguments = parser.parse_args(argv)
    now = datetime.now(UTC)
    try:
        plan = plan_refresh(
            arguments.event,
            arguments.at or now,
            schedule=arguments.schedule,
            manual_month=arguments.month or None,
            now=now,
        )
    except (KeyError, ValueError) as error:
        parser.error(str(error))
    print(f"enabled={str(plan.enabled).lower()}")
    if plan.enabled:
        print(f"month={plan.month}")
        print(f"report_path=data/reports/{plan.month}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
