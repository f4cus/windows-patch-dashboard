from __future__ import annotations

from datetime import date

import pytest

from windows_patch_collector.calendar import (
    most_recent_patch_tuesday_month,
    msrc_document_id,
    patch_tuesday,
    resolve_report_month,
)
from windows_patch_collector.products import (
    WINDOWS_SERVER_23H2,
    WINDOWS_SERVER_2012,
    WINDOWS_SERVER_2012_R2,
    combine_windows_11_identities,
    map_microsoft_product_name,
)


@pytest.mark.parametrize(
    ("month", "expected"),
    [("2026-08", "2026-08-11"), ("2025-01", "2025-01-14"), ("2024-10", "2024-10-08")],
)
def test_patch_tuesday_is_the_second_tuesday(month: str, expected: str) -> None:
    assert patch_tuesday(month).isoformat() == expected


def test_month_format_is_strict() -> None:
    with pytest.raises(ValueError, match="YYYY-MM"):
        patch_tuesday("2026-8")
    assert msrc_document_id("2026-08") == "2026-Aug"


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 8, 10), "2026-07"),
        (date(2026, 8, 11), "2026-08"),
        (date(2026, 8, 13), "2026-08"),
        (date(2026, 8, 31), "2026-08"),
        (date(2026, 9, 3), "2026-08"),
        (date(2026, 9, 8), "2026-09"),
        (date(2027, 1, 1), "2026-12"),
    ],
)
def test_automatic_month_uses_latest_occurred_patch_tuesday(today: date, expected: str) -> None:
    assert most_recent_patch_tuesday_month(today) == expected


def test_manual_month_overrides_automatic_month() -> None:
    assert resolve_report_month(date(2026, 8, 1), "2025-02") == "2025-02"


def test_manual_month_is_strictly_validated() -> None:
    with pytest.raises(ValueError, match="YYYY-MM"):
        resolve_report_month(date(2026, 8, 13), "2026-8")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Windows Server 2012", WINDOWS_SERVER_2012),
        ("Windows Server 2012 R2 (Server Core installation)", WINDOWS_SERVER_2012_R2),
        ("Windows Server 2022, 23H2 Edition (Server Core installation)", WINDOWS_SERVER_23H2),
    ],
)
def test_server_product_aliases(name: str, expected: object) -> None:
    assert map_microsoft_product_name(name) == expected


def test_windows_11_architectures_map_and_branches_combine() -> None:
    first = map_microsoft_product_name("Windows 11 Version 24H2 for x64-based Systems")
    second = map_microsoft_product_name("Windows 11 Version 25H2 for ARM64-based Systems")
    assert first is not None and second is not None
    combined = combine_windows_11_identities([second, first, first])
    assert combined.version == "24H2/25H2"
    assert combined.display_name == "Windows 11 24H2/25H2"
