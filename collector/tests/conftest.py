from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from windows_patch_collector.validation import load_schema


@pytest.fixture(scope="session")
def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def schema(repository_root: Path) -> dict[str, Any]:
    return load_schema(repository_root)


@pytest.fixture
def make_update() -> Iterator[Any]:
    counter = 100000

    def factory(
        *,
        kb: str | None = None,
        display_name: str = "Windows Server 2022",
        release_date: str | None = "2026-08-11",
        update_type: str = "security",
        known_issues_status: str = "none",
        superseded_by: str | None = None,
        include_sources: bool = False,
    ) -> dict[str, Any]:
        nonlocal counter
        counter += 1
        versions = {
            "Windows Server 2012 (ESU)": ("Windows Server", "2012", "ESU"),
            "Windows Server 2012 R2 (ESU)": ("Windows Server", "2012 R2", "ESU"),
            "Windows Server 2016": ("Windows Server", "2016", None),
            "Windows Server 2019": ("Windows Server", "2019", None),
            "Windows Server 2022": ("Windows Server", "2022", None),
            "Windows Server 2025": ("Windows Server", "2025", None),
        }
        if display_name.startswith("Windows 11 "):
            family, version, channel = "Windows 11", display_name.removeprefix("Windows 11 "), None
        else:
            family, version, channel = versions[display_name]

        update: dict[str, Any] = {
            "kb": kb or f"KB{counter}",
            "os": {
                "family": family,
                "version": version,
                "channel": channel,
                "displayName": display_name,
            },
            "updateType": update_type,
            "releaseDate": release_date,
            "changesSummary": "Resumen de cambios.",
            "resolvedIssuesSummary": "Resumen de correcciones.",
            "knownIssuesSummary": "Estado documentado por Microsoft.",
            "knownIssuesStatus": known_issues_status,
            "supersededBy": superseded_by,
        }
        if include_sources:
            update["sources"] = [
                {
                    "type": "microsoft-support",
                    "url": "https://support.microsoft.com/help/5000000",
                    "retrievedAt": "2026-08-12T12:00:00Z",
                }
            ]
        return update

    yield factory


@pytest.fixture
def make_report() -> Iterator[Any]:
    def factory(
        updates: list[dict[str, Any]], *, status: str = "manual-golden-fixture"
    ) -> dict[str, Any]:
        return {
            "schemaVersion": "1.0.0",
            "reportMonth": "2026-08",
            "patchTuesdayDate": "2026-08-11",
            "generatedAt": None,
            "status": status,
            "updates": updates,
        }

    yield factory
