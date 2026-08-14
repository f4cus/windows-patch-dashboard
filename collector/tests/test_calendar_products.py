from __future__ import annotations

import pytest

from windows_patch_collector.calendar import msrc_document_id, patch_tuesday
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
