from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from windows_patch_collector.validation import ReportValidationError, validate_document

UpdateFactory = Callable[..., dict[str, Any]]
ReportFactory = Callable[..., dict[str, Any]]


def test_monthly_and_oob_records_coexist_with_explicit_supersedence(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    monthly = make_update(
        kb="KB5000001",
        known_issues_status="open",
        superseded_by="KB5000002",
    )
    oob = make_update(
        kb="KB5000002",
        release_date="2026-08-15",
        update_type="oob",
        known_issues_status="resolved",
    )

    validate_document(make_report([monthly, oob]), schema)


@pytest.mark.parametrize("known_issues_status", ["open", "resolved", "none", "unknown"])
def test_supersedence_is_independent_from_known_issue_state(
    known_issues_status: str,
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    monthly = make_update(
        kb="KB5000001",
        known_issues_status=known_issues_status,
        superseded_by="KB5000002",
    )
    oob = make_update(
        kb="KB5000002",
        release_date="2026-08-15",
        update_type="oob",
        known_issues_status="resolved",
    )

    validate_document(make_report([monthly, oob]), schema)


def test_superseded_by_must_resolve_to_oob_record_in_same_report(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    monthly = make_update(
        kb="KB5000001",
        known_issues_status="open",
        superseded_by="KB5000002",
    )

    with pytest.raises(ReportValidationError, match="same monthly report"):
        validate_document(make_report([monthly]), schema)


def test_standalone_oob_record_is_rejected(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    oob = make_update(kb="KB5000002", update_type="oob")

    with pytest.raises(ReportValidationError, match="linked from the record it supersedes"):
        validate_document(make_report([oob]), schema)


def test_supersedence_cannot_point_to_a_regular_update(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    monthly = make_update(
        kb="KB5000001",
        known_issues_status="open",
        superseded_by="KB5000002",
    )
    target = make_update(kb="KB5000002", release_date="2026-08-15")

    with pytest.raises(ReportValidationError, match="out-of-band update"):
        validate_document(make_report([monthly, target]), schema)


def test_supersedence_cannot_cross_os_identities(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    monthly = make_update(
        kb="KB5000001",
        display_name="Windows Server 2022",
        known_issues_status="open",
        superseded_by="KB5000002",
    )
    oob = make_update(
        kb="KB5000002",
        display_name="Windows Server 2025",
        release_date="2026-08-15",
        update_type="oob",
        known_issues_status="resolved",
    )

    with pytest.raises(ReportValidationError, match="same normalized OS"):
        validate_document(make_report([monthly, oob]), schema)


def test_superseding_oob_update_must_be_later(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    monthly = make_update(
        kb="KB5000001",
        known_issues_status="open",
        superseded_by="KB5000002",
    )
    oob = make_update(
        kb="KB5000002",
        release_date="2026-08-10",
        update_type="oob",
        known_issues_status="resolved",
    )

    with pytest.raises(ReportValidationError, match="later release date"):
        validate_document(make_report([oob, monthly]), schema)


def test_supersedence_target_must_be_unambiguous(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    monthly = make_update(
        kb="KB5000001",
        known_issues_status="open",
        superseded_by="KB5000002",
    )
    first_oob = make_update(
        kb="KB5000002",
        release_date="2026-08-15",
        update_type="oob",
        known_issues_status="resolved",
    )
    second_oob = dict(first_oob)
    second_oob["changesSummary"] = "Otro resumen de cambios."

    with pytest.raises(ReportValidationError, match="ambiguous"):
        validate_document(make_report([monthly, first_oob, second_oob]), schema)


def test_supersedence_cycles_are_rejected(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    first_oob = make_update(
        kb="KB5000001",
        update_type="oob",
        known_issues_status="open",
        superseded_by="KB5000002",
    )
    second_oob = make_update(
        kb="KB5000002",
        release_date="2026-08-15",
        update_type="oob",
        known_issues_status="resolved",
        superseded_by="KB5000001",
    )

    with pytest.raises(ReportValidationError, match="must not form a cycle"):
        validate_document(make_report([first_oob, second_oob]), schema)
