"""Small, deterministic helpers used by report-refresh automation."""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from windows_patch_collector.calendar import parse_report_month


def report_path(repository_root: Path, month: str) -> Path:
    """Return the only production report path allowed for a report month."""

    parse_report_month(month)
    return repository_root / "data" / "reports" / f"{month}.json"


def semantic_report(document: dict[str, Any]) -> dict[str, Any]:
    """Remove only volatile collection timestamps from a report copy."""

    normalized = deepcopy(document)
    normalized.pop("generatedAt", None)

    updates = normalized.get("updates")
    if isinstance(updates, list):
        for update in updates:
            if not isinstance(update, dict):
                continue
            sources = update.get("sources")
            if not isinstance(sources, list):
                continue
            for source in sources:
                if isinstance(source, dict):
                    source.pop("retrievedAt", None)
    return normalized


def reports_are_semantically_equal(first: Path, second: Path) -> bool:
    """Compare reports while ignoring only their volatile timestamps."""

    with first.open(encoding="utf-8") as first_handle:
        first_document = json.load(first_handle)
    with second.open(encoding="utf-8") as second_handle:
        second_document = json.load(second_handle)
    if not isinstance(first_document, dict) or not isinstance(second_document, dict):
        raise ValueError("Monthly reports must be JSON objects")
    return semantic_report(first_document) == semantic_report(second_document)


def _restore_file(source: Path, destination: Path) -> None:
    """Restore a baseline atomically without changing its contents."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(source.read_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def reconcile_generated_report(baseline: Path, generated: Path) -> bool:
    """Restore timestamp-only changes and return whether content changed."""

    if not baseline.is_file():
        return True
    if not reports_are_semantically_equal(baseline, generated):
        return True
    _restore_file(baseline, generated)
    return False
