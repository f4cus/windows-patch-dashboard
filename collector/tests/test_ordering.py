from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from windows_patch_collector.ordering import CANONICAL_SERVER_ORDER, sort_updates
from windows_patch_collector.validation import ReportValidationError, validate_document

UpdateFactory = Callable[..., dict[str, Any]]
ReportFactory = Callable[..., dict[str, Any]]


def test_canonical_os_order_is_server_then_oldest_windows_11_branch(
    make_update: UpdateFactory,
) -> None:
    display_names = [
        "Windows 11 26H1",
        "Windows Server 2022",
        "Windows Server 2012 R2 (ESU)",
        "Windows 11 24H2/25H2",
        "Windows Server 2025",
        "Windows Server, version 23H2",
        "Windows Server 2012 (ESU)",
        "Windows Server 2019",
        "Windows 11 23H2",
        "Windows Server 2016",
    ]
    updates = [make_update(display_name=name) for name in display_names]

    ordered_names = [update["os"]["displayName"] for update in sort_updates(updates)]

    assert ordered_names == [
        *CANONICAL_SERVER_ORDER,
        "Windows 11 23H2",
        "Windows 11 24H2/25H2",
        "Windows 11 26H1",
    ]

    assert (
        CANONICAL_SERVER_ORDER.index("Windows Server 2022")
        < (CANONICAL_SERVER_ORDER.index("Windows Server, version 23H2"))
        < CANONICAL_SERVER_ORDER.index("Windows Server 2025")
    )


def test_sort_updates_is_deterministic_without_mutating_input(
    make_update: UpdateFactory,
) -> None:
    updates = [
        make_update(kb="KB5000002", display_name="Windows 11 26H1"),
        make_update(kb="KB5000001", display_name="Windows Server 2016"),
    ]
    snapshot = list(updates)

    first = sort_updates(updates)
    second = sort_updates(reversed(updates))

    assert first == second
    assert updates == snapshot


def test_persisted_report_must_use_canonical_order(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    updates = [
        make_update(display_name="Windows 11 23H2"),
        make_update(display_name="Windows Server 2025"),
    ]

    with pytest.raises(ReportValidationError, match="canonical server-first"):
        validate_document(make_report(updates), schema)


def test_duplicate_kb_for_same_os_identity_is_rejected(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    first = make_update(kb="KB5000001", display_name="Windows Server 2022")
    second = make_update(kb="KB5000001", display_name="Windows Server 2022")
    second["changesSummary"] = "Otro resumen de cambios."

    with pytest.raises(ReportValidationError, match="duplicate KB"):
        validate_document(make_report([first, second]), schema)


def test_same_kb_may_be_used_for_distinct_os_identities(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    updates = [
        make_update(kb="KB5000001", display_name="Windows Server 2022"),
        make_update(kb="KB5000001", display_name="Windows Server 2025"),
    ]

    validate_document(make_report(updates), schema)
