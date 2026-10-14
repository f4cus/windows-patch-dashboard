from __future__ import annotations

import calendar
import json
import re
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest

from windows_patch_collector import cli, refresh_schedule
from windows_patch_collector.automation import ensure_refresh_publishable
from windows_patch_collector.calendar import (
    ART,
    patch_tuesday,
    refresh_times,
    resolve_report_month_at,
)
from windows_patch_collector.cli import main as collector_main
from windows_patch_collector.refresh_schedule import CRON_SLOTS, MAX_DELAY, plan_refresh

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("day", "times"),
    [
        (9, [time(15)]),
        (10, [time(h, 15) for h in range(14, 23)]),
        (11, [time(h) for h in range(9, 22, 2)]),
        (12, [time(h) for h in range(9, 22, 4)]),
        (13, [time(9), time(15)]),
        (14, [time(15)]),
        (30, [time(15)]),
    ],
)
def test_november_approved_windows(day: int, times: list[time]) -> None:
    assert patch_tuesday("2026-11") == date(2026, 11, 10)
    assert refresh_times(date(2026, 11, day)) == tuple(times)


@pytest.mark.parametrize(
    ("stamp", "month"),
    [
        ("2026-11-10T02:59:59Z", "2026-10"),
        ("2026-11-10T17:14:59Z", "2026-10"),
        ("2026-11-10T17:15:00Z", "2026-11"),
        ("2026-11-11T01:15:00Z", "2026-11"),
        ("2026-12-01T02:59:59Z", "2026-11"),
        ("2027-01-01T02:59:59Z", "2026-12"),
        ("2027-01-12T17:14:59Z", "2026-12"),
        ("2027-01-12T17:15:00Z", "2027-01"),
    ],
)
def test_month_selection_waits_for_art_opening(stamp: str, month: str) -> None:
    assert resolve_report_month_at(datetime.fromisoformat(stamp)) == month


def test_manual_override_and_push_are_preserved(capsys: pytest.CaptureFixture[str]) -> None:
    instant = datetime(2026, 11, 10, 8, tzinfo=ART)
    assert plan_refresh("workflow_dispatch", instant).month == "2026-10"
    assert plan_refresh("workflow_dispatch", instant, manual_month="2025-02").month == "2025-02"
    assert not plan_refresh("push", instant).enabled
    assert collector_main(["target-month", "--today", "2026-11-10"]) == 0
    assert capsys.readouterr().out.strip() == "2026-10"
    assert collector_main(["target-month", "--month", "2025-02"]) == 0
    assert capsys.readouterr().out.strip() == "2025-02"
    with pytest.raises(ValueError, match="YYYY-MM"):
        plan_refresh("workflow_dispatch", instant, manual_month="2025-2")


@pytest.mark.parametrize(
    ("cron", "stamp", "enabled", "art_day"),
    [
        ("15 17-23 * * 2", "2026-11-10T17:14:59Z", False, None),
        ("15 17-23 * * 2", "2026-11-10T17:15:00Z", True, 10),
        ("15 0,1 * * 3", "2026-11-11T00:59:00Z", True, 10),
        ("15 0,1 * * 3", "2026-11-11T02:30:00Z", True, 10),
        ("0 0 * * 4,5", "2026-11-12T00:50:00Z", True, 11),
        ("0 0 * * 4,5", "2026-11-13T02:45:00Z", True, 12),
        ("0 18 * * *", "2026-11-10T18:40:00Z", False, None),
        ("0 18 * * *", "2026-11-11T18:40:00Z", True, 11),
        ("0 18 * * *", "2026-11-12T18:40:00Z", False, None),
        ("0 18 * * *", "2026-11-13T18:40:00Z", True, 13),
        ("0 12 * * 5", "2026-11-20T12:05:00Z", False, None),
        ("0 18 * * *", "2026-12-01T00:00:00Z", True, 30),
        ("0 18 * * *", "2027-01-01T00:00:00Z", True, 31),
    ],
)
def test_delayed_triggers_and_midnight(
    cron: str, stamp: str, enabled: bool, art_day: int | None
) -> None:
    instant = datetime.fromisoformat(stamp)
    plan = plan_refresh("schedule", instant, schedule=cron)
    assert plan.enabled is enabled
    if enabled:
        assert plan.slot is not None
        assert plan.slot.astimezone(ART).day == art_day


def test_queue_delays_are_anchored_and_bounded() -> None:
    created = datetime(2026, 11, 11, 1, 20, tzinfo=UTC)
    slot = created.replace(minute=15)
    plan = plan_refresh("schedule", created, schedule="15 0,1 * * 3", now=slot + MAX_DELAY)
    assert plan.enabled and plan.slot == slot and plan.month == "2026-11"
    assert not plan_refresh(
        "schedule", created, schedule="15 0,1 * * 3", now=slot + MAX_DELAY + timedelta(seconds=1)
    ).enabled
    assert not plan_refresh(
        "schedule", created, schedule="15 0,1 * * 3", now=slot - timedelta(seconds=1)
    ).enabled
    # An omitted 14:15 trigger is not replayed by the daily cron at 15:00 on D.
    assert not plan_refresh(
        "schedule", datetime(2026, 11, 10, 18, tzinfo=UTC), schedule="0 18 * * *"
    ).enabled


@pytest.mark.parametrize("year", [2026, 2027])
def test_workflow_crons_cover_exactly_the_approved_slots_without_duplicates(year: int) -> None:
    workflow = (ROOT / ".github/workflows/pages.yml").read_text("utf-8")
    crons = re.findall(r'cron: "([^"]+)"', workflow)
    assert len(crons) == len(set(crons))
    assert set(crons) == set(CRON_SLOTS)
    for month in range(1, 13):
        second_tuesday = patch_tuesday(f"{year}-{month:02d}")
        assert second_tuesday.weekday() == calendar.TUESDAY
        assert 8 <= second_tuesday.day <= 14
        for day_number in range(1, calendar.monthrange(year, month)[1] + 1):
            local_day = date(year, month, day_number)
            candidates: list[datetime] = []
            for utc_day in (local_day, local_day + timedelta(days=1)):
                for cron in crons:
                    minute, hours, weekdays = CRON_SLOTS[cron]
                    if utc_day.weekday() not in weekdays:
                        continue
                    for hour in hours:
                        slot = datetime.combine(utc_day, time(hour, minute), UTC)
                        if slot.astimezone(ART).date() != local_day:
                            continue
                        if plan_refresh("schedule", slot, schedule=cron).enabled:
                            candidates.append(slot.astimezone(ART))
            assert sorted(value.time() for value in candidates) == list(refresh_times(local_day))
            assert len(candidates) == len(set(candidates))


def test_naive_timestamps_and_unknown_crons_fail_safely() -> None:
    with pytest.raises(ValueError, match="time zone"):
        resolve_report_month_at(datetime(2026, 11, 10))
    with pytest.raises(ValueError, match="time zone"):
        plan_refresh("schedule", datetime(2026, 11, 10))
    with pytest.raises(KeyError):
        plan_refresh("schedule", datetime(2026, 11, 10, tzinfo=UTC), schedule="unexpected")


def _publication_report(path: Path, month: str) -> None:
    path.write_text(
        json.dumps(
            {
                "reportMonth": month,
                "updates": [
                    {
                        "kb": "KB5999999",  # Synthetic publication evidence, not Microsoft data.
                        "updateType": "security",
                        "releaseDate": patch_tuesday(month).isoformat(),
                        "sources": [{"type": "msrc"}, {"type": "microsoft-support"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("month", "opening"),
    [("2026-11", "2026-11-10T18:00:00Z"), ("2026-07", "2026-07-14T17:00:00Z")],
)
def test_publication_waits_for_pacific_release_time(
    tmp_path: Path, month: str, opening: str
) -> None:
    report = tmp_path / "report.json"
    _publication_report(report, month)
    instant = datetime.fromisoformat(opening)
    with pytest.raises(ValueError, match="10:00 Pacific"):
        ensure_refresh_publishable(report, instant - timedelta(seconds=1))
    ensure_refresh_publishable(report, instant)


@pytest.mark.parametrize("missing", ["all", "support", "monthly", "release-date", "kb"])
def test_missing_publication_evidence_cannot_be_committed(tmp_path: Path, missing: str) -> None:
    report = tmp_path / "report.json"
    _publication_report(report, "2026-11")
    document = json.loads(report.read_text("utf-8"))
    update = document["updates"][0]
    if missing == "all":
        document["updates"] = []
    elif missing == "support":
        update["sources"] = [{"type": "msrc"}]
    elif missing == "monthly":
        update["updateType"] = "oob"
    elif missing == "release-date":
        update["releaseDate"] = "2026-11-11"
    else:
        update["kb"] = "NO PUBLICADO"
    report.write_text(json.dumps(document), encoding="utf-8")
    original = report.read_bytes()
    with pytest.raises(ValueError, match="Support-verified"):
        ensure_refresh_publishable(report, datetime(2026, 11, 10, 19, tzinfo=UTC))
    assert report.read_bytes() == original


@pytest.mark.parametrize(
    ("stamp", "month"),
    [("2026-11-10T17:14:59Z", "2026-10"), ("2026-11-10T17:15:00Z", "2026-11")],
)
def test_target_cli_uses_the_actual_instant(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], stamp: str, month: str
) -> None:
    class Clock(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime.fromisoformat(stamp)

    monkeypatch.setattr(cli, "datetime", Clock)
    assert collector_main(["target-month"]) == 0
    assert capsys.readouterr().out.strip() == month


def test_schedule_cli_outputs_only_enabled_target(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class Clock(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            return datetime(2026, 11, 10, 18, 20, tzinfo=UTC)

    monkeypatch.setattr(refresh_schedule, "datetime", Clock)
    assert (
        refresh_schedule.main(
            ["--event", "schedule", "--schedule", "0 18 * * *", "--at", "2026-11-10T18:01:00Z"]
        )
        == 0
    )
    assert capsys.readouterr().out.strip() == "enabled=false"
    assert (
        refresh_schedule.main(
            ["--event", "schedule", "--schedule", "15 17-23 * * 2", "--at", "2026-11-10T17:20:00Z"]
        )
        == 0
    )
    assert capsys.readouterr().out.splitlines() == [
        "enabled=true",
        "month=2026-11",
        "report_path=data/reports/2026-11.json",
    ]


def test_pre_release_cli_fails_before_reconciliation_and_preserves_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    month = "2099-11"
    report = tmp_path / "data" / "reports" / f"{month}.json"
    report.parent.mkdir(parents=True)
    _publication_report(report, month)
    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"previous": "valid committed content"}', encoding="utf-8")
    original_report, original_baseline = report.read_bytes(), baseline.read_bytes()
    assert (
        collector_main(
            [
                "reconcile-report",
                "--month",
                month,
                "--root",
                str(tmp_path),
                "--baseline",
                str(baseline),
                "--require-release",
            ]
        )
        == 1
    )
    assert "10:00 Pacific" in capsys.readouterr().out
    assert (report.read_bytes(), baseline.read_bytes()) == (original_report, original_baseline)
