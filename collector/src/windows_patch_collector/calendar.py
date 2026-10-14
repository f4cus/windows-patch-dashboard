"""Deterministic monthly scheduling calculations."""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time, timedelta, timezone

_MONTH_PATTERN = re.compile(r"^(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])$")
ART = timezone(timedelta(hours=-3), name="ART")


def parse_report_month(value: str) -> tuple[int, int]:
    """Parse a strict ``YYYY-MM`` report month."""

    match = _MONTH_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(f"Invalid report month {value!r}; expected YYYY-MM")
    return int(match.group("year")), int(match.group("month"))


def patch_tuesday(value: str) -> date:
    """Return the second Tuesday for a strict report month."""

    year, month = parse_report_month(value)
    first_weekday, _ = calendar.monthrange(year, month)
    first_tuesday = 1 + (calendar.TUESDAY - first_weekday) % 7
    return date(year, month, first_tuesday + 7)


def msrc_document_id(value: str) -> str:
    """Return the MSRC monthly document identifier for a report month."""

    year, month = parse_report_month(value)
    return f"{year}-{calendar.month_abbr[month]}"


def most_recent_patch_tuesday_month(today: date) -> str:
    """Return the latest report month whose Patch Tuesday has occurred."""

    current_month = today.strftime("%Y-%m")
    if today >= patch_tuesday(current_month):
        return current_month

    previous_month = today.replace(day=1) - timedelta(days=1)
    return previous_month.strftime("%Y-%m")


def resolve_report_month(today: date, manual_month: str | None = None) -> str:
    """Validate an explicit month or calculate the latest eligible month."""

    if manual_month is not None:
        parse_report_month(manual_month)
        return manual_month
    return most_recent_patch_tuesday_month(today)


def resolve_report_month_at(instant: datetime, manual_month: str | None = None) -> str:
    """Enable the new month only from D at 14:15 ART; preserve manual overrides."""

    if instant.tzinfo is None:
        raise ValueError("An explicit time zone is required")
    local = instant.astimezone(ART)
    if manual_month is not None:
        return resolve_report_month(local.date(), manual_month)
    month = local.strftime("%Y-%m")
    opening = datetime.combine(patch_tuesday(month), time(14, 15), ART)
    if local >= opening:
        return month
    return (local.date().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")


def refresh_times(day: date) -> tuple[time, ...]:
    """Return approved ART slots, including daily refreshes before the next D."""

    offset = (day - patch_tuesday(day.strftime("%Y-%m"))).days
    if offset == 0:
        return tuple(time(hour, 15) for hour in range(14, 23))
    if offset == 1:
        return tuple(time(hour) for hour in range(9, 22, 2))
    if offset == 2:
        return tuple(time(hour) for hour in range(9, 22, 4))
    if offset == 3:
        return (time(9), time(15))
    return (time(15),)
