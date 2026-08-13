from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from windows_patch_collector.validation import ReportValidationError, validate_document

UpdateFactory = Callable[..., dict[str, Any]]
ReportFactory = Callable[..., dict[str, Any]]


@pytest.mark.parametrize("kb", ["KB1", "KB5121003"])
def test_numeric_kb_values_are_valid(
    kb: str,
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    validate_document(make_report([make_update(kb=kb)]), schema)


def test_no_publicado_is_valid_only_with_explicit_missing_semantics(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update(
        kb="NO PUBLICADO",
        display_name="Windows Server 2012 (ESU)",
        release_date=None,
        update_type="esu",
        known_issues_status="not-published",
    )

    validate_document(make_report([update]), schema)


@pytest.mark.parametrize("kb", ["5121003", "kb5121003", "KB", "KB12A", "NO PUBLICADO "])
def test_malformed_kb_values_are_rejected(
    kb: str,
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    with pytest.raises(ReportValidationError):
        validate_document(make_report([make_update(kb=kb)]), schema)


def test_no_publicado_cannot_claim_no_known_issues(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update(
        kb="NO PUBLICADO",
        display_name="Windows Server 2012 (ESU)",
        release_date=None,
        update_type="esu",
        known_issues_status="none",
    )

    with pytest.raises(ReportValidationError):
        validate_document(make_report([update]), schema)


@pytest.mark.parametrize(
    ("field", "value"),
    [("releaseDate", "2026-08-11"), ("supersededBy", "KB5000001")],
)
def test_no_publicado_cannot_claim_published_update_metadata(
    field: str,
    value: str,
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update(
        kb="NO PUBLICADO",
        display_name="Windows Server 2012 (ESU)",
        release_date=None,
        update_type="esu",
        known_issues_status="not-published",
    )
    update[field] = value

    with pytest.raises(ReportValidationError):
        validate_document(make_report([update]), schema)


def test_published_kb_cannot_use_not_published_status(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update(known_issues_status="not-published")

    with pytest.raises(ReportValidationError):
        validate_document(make_report([update]), schema)


def test_unknown_known_issue_state_remains_representable(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update(known_issues_status="unknown")

    validate_document(make_report([update]), schema)


def test_oob_status_requires_a_superseding_kb(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update(known_issues_status="oob")

    with pytest.raises(ReportValidationError):
        validate_document(make_report([update]), schema)


@pytest.mark.parametrize("status", ["generated", "partial", "verified"])
@pytest.mark.parametrize("sources", ["omitted", "empty"])
def test_non_manual_reports_require_provenance_per_update(
    status: str,
    sources: str,
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update()
    if sources == "empty":
        update["sources"] = []

    with pytest.raises(ReportValidationError):
        validate_document(make_report([update], status=status), schema)


def test_manual_golden_fixture_may_omit_sources(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update()

    validate_document(make_report([update]), schema)


@pytest.mark.parametrize("status", ["generated", "partial", "verified"])
def test_non_manual_reports_accept_official_provenance(
    status: str,
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update(include_sources=True)

    validate_document(make_report([update], status=status), schema)


def test_source_type_cannot_disguise_a_third_party_url(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update(include_sources=True)
    update["sources"][0]["url"] = "https://example.com/not-microsoft"

    with pytest.raises(ReportValidationError):
        validate_document(make_report([update], status="generated"), schema)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reportMonth", "2026-09"),
        ("patchTuesdayDate", "2026-08-12"),
        ("generatedAt", "2026-08-12T12:00:00Z"),
    ],
)
def test_manual_golden_fixture_metadata_is_fixed(
    field: str,
    value: str,
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    report = make_report([make_update()])
    report[field] = value

    with pytest.raises(ReportValidationError):
        validate_document(report, schema)


def test_manual_golden_fixture_requires_null_generated_at(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    report = make_report([make_update()])
    del report["generatedAt"]

    with pytest.raises(ReportValidationError):
        validate_document(report, schema)


def test_windows_11_display_name_must_match_version(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update(display_name="Windows 11 23H2")
    update["os"]["displayName"] = "Windows 11 26H1"

    with pytest.raises(ReportValidationError, match="derived exactly"):
        validate_document(make_report([update]), schema)


@pytest.mark.parametrize("version", ["24H2/24H2", "25H2/24H2"])
def test_combined_windows_11_branches_must_be_unique_and_ordered(
    version: str,
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update(display_name="Windows 11 24H2/25H2")
    update["os"]["version"] = version
    update["os"]["displayName"] = f"Windows 11 {version}"

    with pytest.raises(ReportValidationError, match="combined Windows 11 branches"):
        validate_document(make_report([update]), schema)


def test_windows_11_channel_must_be_null(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update(display_name="Windows 11 23H2")
    update["os"]["channel"] = "GA"

    with pytest.raises(ReportValidationError):
        validate_document(make_report([update]), schema)


def test_esu_update_type_requires_an_esu_os(
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    update = make_update(display_name="Windows Server 2022", update_type="esu")

    with pytest.raises(ReportValidationError):
        validate_document(make_report([update]), schema)
