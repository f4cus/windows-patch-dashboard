from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from windows_patch_collector.errors import CollectionConflictError
from windows_patch_collector.models import StructuredResult, StructuredUpdate, SupportArticle
from windows_patch_collector.normalization import normalize_report
from windows_patch_collector.output import write_report_atomic
from windows_patch_collector.products import WINDOWS_SERVER_2022
from windows_patch_collector.validation import ReportValidationError, load_schema, validate_document

MSRC_URL = "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Aug"
SUPPORT_URL = "https://support.microsoft.com/en-us/help/5120242/article"
STAMP = datetime(2026, 8, 13, 12, tzinfo=UTC)


def _update(
    kb: str = "KB5120242",
    *,
    release: date = date(2026, 8, 11),
    update_type: str = "security",
    subtype: str = "Security Update",
    supersedes: str | None = None,
) -> StructuredUpdate:
    return StructuredUpdate(  # type: ignore[arg-type]
        kb,
        WINDOWS_SERVER_2022,
        release,
        update_type,
        MSRC_URL,
        STAMP,
        subtype,
        supersedes=supersedes,
    )


def _article(kb: str, release: date) -> SupportArticle:
    return SupportArticle(
        kb,
        release,
        SUPPORT_URL.replace("5120242", kb.removeprefix("KB")),
        STAMP,
        "This update includes verified security improvements.",
        "This update addresses a verified reliability issue.",
        "Microsoft is not currently aware of any issues with this update.",
        "none",
    )


def test_normalization_emits_no_publicado_and_provenance(schema: dict[str, object]) -> None:
    structured = StructuredResult((_update(),), MSRC_URL, STAMP)
    result = normalize_report(
        month="2026-08",
        structured=structured,
        support_articles={"KB5120242": _article("KB5120242", date(2026, 8, 11))},
        support_failures={},
        generated_at=STAMP,
    )
    validate_document(result.document, schema)

    rows = result.document["updates"]
    assert isinstance(rows, list)
    unpublished = [row for row in rows if row["kb"] == "NO PUBLICADO"]
    assert [row["os"]["version"] for row in unpublished] == ["2012", "2012 R2"]
    assert all(row["knownIssuesStatus"] == "not-published" for row in unpublished)
    published = next(row for row in rows if row["kb"] == "KB5120242")
    assert [source["type"] for source in published["sources"]] == [
        "msrc",
        "microsoft-support",
    ]
    assert all(source["retrievedAt"] == "2026-08-13T12:00:00Z" for source in published["sources"])


def test_missing_support_is_unknown_and_does_not_claim_unused_provenance() -> None:
    result = normalize_report(
        month="2026-08",
        structured=StructuredResult((_update(),), MSRC_URL, STAMP),
        support_articles={},
        support_failures={"KB5120242": "HTTP 503"},
        generated_at=STAMP,
    )
    row = next(row for row in result.document["updates"] if row["kb"] == "KB5120242")
    assert row["knownIssuesStatus"] == "unknown"
    assert [source["type"] for source in row["sources"]] == ["msrc"]
    assert result.document["status"] == "partial"


def test_duplicate_conflict_is_rejected() -> None:
    structured = StructuredResult((_update(), _update(subtype="Monthly Rollup")), MSRC_URL, STAMP)
    with pytest.raises(CollectionConflictError, match="conflicting records"):
        normalize_report(
            month="2026-08",
            structured=structured,
            support_articles={},
            support_failures={},
            generated_at=STAMP,
        )


def test_explicit_oob_relationship_is_represented_and_validated(schema: dict[str, object]) -> None:
    monthly = _update()
    oob = _update(
        "KB5120999",
        release=date(2026, 8, 18),
        update_type="oob",
        subtype="Out-of-band Security Update",
        supersedes="KB5120242",
    )
    result = normalize_report(
        month="2026-08",
        structured=StructuredResult((monthly, oob), MSRC_URL, STAMP),
        support_articles={
            monthly.kb: _article(monthly.kb, monthly.release_date),
            oob.kb: _article(oob.kb, oob.release_date),
        },
        support_failures={},
        generated_at=STAMP,
    )
    validate_document(result.document, schema)
    rows = result.document["updates"]
    base = next(row for row in rows if row["kb"] == monthly.kb)
    target = next(row for row in rows if row["kb"] == oob.kb)
    assert base["supersededBy"] == oob.kb
    assert target["updateType"] == "oob"
    assert target["supersededBy"] is None


def test_atomic_writer_preserves_existing_file_on_invalid_document(
    tmp_path: Path, repository_root: Path
) -> None:
    destination = tmp_path / "2026-08.json"
    destination.write_text("existing valid report placeholder", encoding="utf-8")
    with pytest.raises(ReportValidationError):
        write_report_atomic({}, repository_root=repository_root, destination=destination)
    assert destination.read_text(encoding="utf-8") == "existing valid report placeholder"


def test_atomic_writer_writes_valid_report(tmp_path: Path, repository_root: Path) -> None:
    fixture = json.loads(
        (repository_root / "data" / "fixtures" / "2026-08.json").read_text(encoding="utf-8")
    )
    fixture["status"] = "generated"
    fixture["generatedAt"] = "2026-08-13T12:00:00Z"
    for update in fixture["updates"]:
        update["sources"] = [
            {"type": "msrc", "url": MSRC_URL, "retrievedAt": "2026-08-13T12:00:00Z"}
        ]
    validate_document(fixture, load_schema(repository_root))
    destination = tmp_path / "2026-08.json"
    write_report_atomic(fixture, repository_root=repository_root, destination=destination)
    assert json.loads(destination.read_text(encoding="utf-8"))["status"] == "generated"
    assert not list(tmp_path.glob("*.tmp"))
