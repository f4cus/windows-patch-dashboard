from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from windows_patch_collector.validation import ReportValidationError, validate_repository

UpdateFactory = Callable[..., dict[str, Any]]
ReportFactory = Callable[..., dict[str, Any]]


def test_every_fixture_and_report_validates(repository_root: Path) -> None:
    validated_paths = validate_repository(repository_root)

    assert repository_root / "data/fixtures/2026-08.json" in validated_paths


@pytest.mark.parametrize(
    ("relative_path", "is_allowed"),
    [
        (Path("data/fixtures/2026-08.json"), True),
        (Path("data/fixtures/2026-09.json"), False),
        (Path("data/reports/2026-08.json"), False),
    ],
)
def test_manual_golden_status_is_reserved_for_exact_fixture_path(
    relative_path: Path,
    is_allowed: bool,
    tmp_path: Path,
    schema: dict[str, Any],
    make_update: UpdateFactory,
    make_report: ReportFactory,
) -> None:
    schema_path = tmp_path / "data/schema/monthly-report.schema.json"
    schema_path.parent.mkdir(parents=True)
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    report_path = tmp_path / relative_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(make_report([make_update()])), encoding="utf-8")

    if is_allowed:
        assert report_path in validate_repository(tmp_path)
    else:
        with pytest.raises(ReportValidationError, match="reserved"):
            validate_repository(tmp_path)
