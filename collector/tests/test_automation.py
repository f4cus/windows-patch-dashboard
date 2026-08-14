from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from windows_patch_collector.automation import (
    reconcile_generated_report,
    report_path,
    reports_are_semantically_equal,
)


def _report() -> dict[str, object]:
    return {
        "schemaVersion": "1.0.0",
        "reportMonth": "2026-08",
        "generatedAt": "2026-08-13T12:00:00Z",
        "status": "generated",
        "updates": [
            {
                "kb": "KB5120242",
                "knownIssuesStatus": "none",
                "content": {"highlights": "Mejoras", "knownIssues": "Ninguno"},
                "sources": [
                    {
                        "type": "microsoft-support",
                        "url": "https://support.microsoft.com/es-es/help/5120242/article",
                        "retrievedAt": "2026-08-13T12:00:00Z",
                    }
                ],
            }
        ],
    }


def _write(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_expected_report_file_is_selected_from_month(tmp_path: Path) -> None:
    assert report_path(tmp_path, "2026-08") == tmp_path / "data" / "reports" / "2026-08.json"
    with pytest.raises(ValueError, match="YYYY-MM"):
        report_path(tmp_path, "2026-8")


@pytest.mark.parametrize("timestamp_field", ["generatedAt", "retrievedAt"])
def test_timestamp_only_changes_are_equal_and_restore_baseline(
    tmp_path: Path, timestamp_field: str
) -> None:
    baseline = tmp_path / "baseline.json"
    generated = tmp_path / "generated.json"
    original = _report()
    refreshed = deepcopy(original)
    if timestamp_field == "generatedAt":
        refreshed["generatedAt"] = "2026-08-14T12:00:00Z"
    else:
        refreshed["updates"][0]["sources"][0]["retrievedAt"] = (  # type: ignore[index]
            "2026-08-14T12:00:00Z"
        )
    _write(baseline, original)
    _write(generated, refreshed)

    assert reports_are_semantically_equal(baseline, generated)
    assert reconcile_generated_report(baseline, generated) is False
    assert generated.read_bytes() == baseline.read_bytes()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kb", "KB5999999"),
        ("knownIssuesStatus", "open"),
        ("reportStatus", "partial"),
        ("content", {"highlights": "Cambio sustantivo", "knownIssues": "Ninguno"}),
        ("sourceUrl", "https://support.microsoft.com/es-es/help/5999999/article"),
    ],
)
def test_substantive_changes_are_detected(tmp_path: Path, field: str, value: object) -> None:
    baseline = tmp_path / "baseline.json"
    generated = tmp_path / "generated.json"
    original = _report()
    changed = deepcopy(original)
    update = changed["updates"][0]  # type: ignore[index]
    if field == "reportStatus":
        changed["status"] = value
    elif field == "sourceUrl":
        update["sources"][0]["url"] = value  # type: ignore[index]
    else:
        update[field] = value  # type: ignore[index]
    _write(baseline, original)
    _write(generated, changed)

    assert not reports_are_semantically_equal(baseline, generated)
    before = generated.read_bytes()
    assert reconcile_generated_report(baseline, generated) is True
    assert generated.read_bytes() == before


def test_missing_baseline_is_a_substantive_new_report(tmp_path: Path) -> None:
    generated = tmp_path / "generated.json"
    _write(generated, _report())
    assert reconcile_generated_report(tmp_path / "missing.json", generated) is True
