"""Deterministic monthly scheduling calculations."""

from __future__ import annotations

import calendar
import re
from datetime import date

_MONTH_PATTERN = re.compile(r"^(?P<year>[0-9]{4})-(?P<month>0[1-9]|1[0-2])$")


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
