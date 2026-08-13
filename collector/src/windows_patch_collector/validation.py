"""Schema and cross-record validation for fixture and generated report JSON."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from windows_patch_collector.ordering import sort_updates

SCHEMA_PATH = Path("data/schema/monthly-report.schema.json")
DATA_DIRECTORIES = (Path("data/fixtures"), Path("data/reports"))
GOLDEN_FIXTURE_PATH = Path("data/fixtures/2026-08.json")

OsIdentity = tuple[str, str, str | None]
UpdateKey = tuple[OsIdentity, str]


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One actionable validation failure."""

    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.location}: {self.message}"


class ReportValidationError(ValueError):
    """Raised when a monthly report violates schema or cross-record rules."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__("\n".join(str(issue) for issue in self.issues))


def find_repository_root(start: Path | None = None) -> Path:
    """Find the closest ancestor containing the monthly report schema."""

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / SCHEMA_PATH).is_file():
            return candidate
    raise FileNotFoundError(f"Could not find {SCHEMA_PATH} from {current}")


def load_schema(repository_root: Path) -> dict[str, Any]:
    """Load and check the JSON Schema itself before using it."""

    with (repository_root / SCHEMA_PATH).open(encoding="utf-8") as handle:
        schema: dict[str, Any] = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return schema


def iter_data_files(repository_root: Path) -> list[Path]:
    """Return every fixture and report JSON path in deterministic order."""

    paths: list[Path] = []
    for relative_directory in DATA_DIRECTORIES:
        directory = repository_root / relative_directory
        if directory.is_dir():
            paths.extend(directory.rglob("*.json"))
    return sorted(paths)


def _json_path(parts: Sequence[object]) -> str:
    return "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in parts)


def _os_identity(update: Mapping[str, Any]) -> OsIdentity | None:
    os_value = update.get("os")
    if not isinstance(os_value, Mapping):
        return None

    family = os_value.get("family")
    version = os_value.get("version")
    channel = os_value.get("channel")
    if not isinstance(family, str) or not isinstance(version, str):
        return None
    if channel is not None and not isinstance(channel, str):
        return None
    return (family, version, channel)


def _windows_11_identity_issues(update: Mapping[str, Any], index: int) -> list[ValidationIssue]:
    os_value = update.get("os")
    if not isinstance(os_value, Mapping) or os_value.get("family") != "Windows 11":
        return []

    version = os_value.get("version")
    display_name = os_value.get("displayName")
    if not isinstance(version, str) or not isinstance(display_name, str):
        return []

    issues: list[ValidationIssue] = []
    if display_name != f"Windows 11 {version}":
        issues.append(
            ValidationIssue(
                f"$.updates[{index}].os.displayName",
                "Windows 11 displayName must be derived exactly from os.version",
            )
        )

    branch_labels = version.split("/")
    branch_order = [
        (int(branch_label[:2]), int(branch_label[-1])) for branch_label in branch_labels
    ]
    if len(set(branch_labels)) != len(branch_labels):
        issues.append(
            ValidationIssue(
                f"$.updates[{index}].os.version",
                "combined Windows 11 branches must not contain duplicates",
            )
        )
    elif branch_order != sorted(branch_order):
        issues.append(
            ValidationIssue(
                f"$.updates[{index}].os.version",
                "combined Windows 11 branches must be ordered from oldest to newest",
            )
        )
    return issues


def _supersedence_cycle_issues(edges: Mapping[int, int]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    completed: set[int] = set()
    reported_cycles: set[frozenset[int]] = set()

    for start in edges:
        if start in completed:
            continue

        path: list[int] = []
        positions: dict[int, int] = {}
        current = start
        while current in edges and current not in completed:
            if current in positions:
                cycle = path[positions[current] :]
                signature = frozenset(cycle)
                if signature not in reported_cycles:
                    reported_cycles.add(signature)
                    for index in cycle:
                        issues.append(
                            ValidationIssue(
                                f"$.updates[{index}].supersededBy",
                                "supersedence relationships must not form a cycle",
                            )
                        )
                break
            positions[current] = len(path)
            path.append(current)
            current = edges[current]
        completed.update(path)

    return issues


def _semantic_issues(document: Mapping[str, Any]) -> list[ValidationIssue]:
    updates_value = document.get("updates")
    if not isinstance(updates_value, list):
        return []

    updates = [update for update in updates_value if isinstance(update, Mapping)]
    if len(updates) != len(updates_value):
        return []

    issues: list[ValidationIssue] = []
    if updates != sort_updates(updates):
        issues.append(
            ValidationIssue(
                "$.updates",
                "updates must use the canonical server-first, oldest-Windows-11-first order",
            )
        )

    updates_by_key: dict[UpdateKey, list[int]] = {}
    referenced_oob_keys: set[UpdateKey] = set()
    updates_by_kb: dict[str, list[int]] = {}
    identities: list[OsIdentity | None] = []
    for index, update in enumerate(updates):
        issues.extend(_windows_11_identity_issues(update, index))

        identity = _os_identity(update)
        identities.append(identity)
        kb = update.get("kb")
        if identity is not None and isinstance(kb, str):
            updates_by_key.setdefault((identity, kb), []).append(index)
            updates_by_kb.setdefault(kb, []).append(index)
        superseded_by = update.get("supersededBy")
        if identity is not None and isinstance(superseded_by, str):
            referenced_oob_keys.add((identity, superseded_by))

    for indices in updates_by_key.values():
        for duplicate_index in indices[1:]:
            issues.append(
                ValidationIssue(
                    f"$.updates[{duplicate_index}].kb",
                    "duplicate KB records are not allowed for the same normalized OS identity",
                )
            )

    edges: dict[int, int] = {}
    for index, update in enumerate(updates):
        kb = update.get("kb")
        identity = identities[index]
        superseded_by = update.get("supersededBy")
        if isinstance(superseded_by, str) and identity is not None:
            if superseded_by == kb:
                issues.append(
                    ValidationIssue(
                        f"$.updates[{index}].supersededBy",
                        "an update cannot supersede itself",
                    )
                )
                continue

            targets = updates_by_key.get((identity, superseded_by), [])
            if not targets:
                has_other_os_target = bool(updates_by_kb.get(superseded_by))
                requirement = (
                    "for the same normalized OS"
                    if has_other_os_target
                    else "in the same monthly report for the same normalized OS"
                )
                issues.append(
                    ValidationIssue(
                        f"$.updates[{index}].supersededBy",
                        f"{superseded_by} must identify another update {requirement}",
                    )
                )
            elif len(targets) > 1:
                issues.append(
                    ValidationIssue(
                        f"$.updates[{index}].supersededBy",
                        f"{superseded_by} is ambiguous for this normalized OS",
                    )
                )
            else:
                target_index = targets[0]
                target = updates[target_index]
                edges[index] = target_index
                if target.get("updateType") != "oob":
                    issues.append(
                        ValidationIssue(
                            f"$.updates[{index}].supersededBy",
                            f"{superseded_by} must identify an out-of-band update",
                        )
                    )

                release_date = update.get("releaseDate")
                target_release_date = target.get("releaseDate")
                if (
                    isinstance(release_date, str)
                    and isinstance(target_release_date, str)
                    and date.fromisoformat(target_release_date) <= date.fromisoformat(release_date)
                ):
                    issues.append(
                        ValidationIssue(
                            f"$.updates[{index}].supersededBy",
                            "the superseding out-of-band update must have a later release date",
                        )
                    )

        if (
            update.get("updateType") == "oob"
            and identity is not None
            and isinstance(kb, str)
            and (identity, kb) not in referenced_oob_keys
        ):
            issues.append(
                ValidationIssue(
                    f"$.updates[{index}].kb",
                    "an out-of-band update must be linked from the record it supersedes",
                )
            )

    issues.extend(_supersedence_cycle_issues(edges))
    return issues


def validation_issues(
    document: Mapping[str, Any], schema: Mapping[str, Any]
) -> list[ValidationIssue]:
    """Return schema failures followed by safe cross-record failures."""

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    schema_errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    issues = [
        ValidationIssue(_json_path(list(error.absolute_path)), error.message)
        for error in schema_errors
    ]
    if not issues:
        issues.extend(_semantic_issues(document))
    return issues


def validate_document(document: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    """Raise a consolidated error if a decoded monthly report is invalid."""

    issues = validation_issues(document, schema)
    if issues:
        raise ReportValidationError(issues)


def validate_file(
    path: Path,
    schema: Mapping[str, Any],
    *,
    allow_manual_golden_fixture: bool = False,
) -> None:
    """Decode and validate one report file."""

    try:
        with path.open(encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise ReportValidationError([ValidationIssue(str(path), str(error))]) from error

    if not isinstance(document, Mapping):
        raise ReportValidationError(
            [ValidationIssue(str(path), "the JSON document must be an object")]
        )
    validate_document(document, schema)
    if document.get("status") == "manual-golden-fixture" and not allow_manual_golden_fixture:
        raise ReportValidationError(
            [
                ValidationIssue(
                    "$.status",
                    f"manual-golden-fixture is reserved for {GOLDEN_FIXTURE_PATH}",
                )
            ]
        )


def validate_repository(repository_root: Path) -> list[Path]:
    """Validate every JSON file under data/fixtures and data/reports."""

    root = repository_root.resolve()
    schema = load_schema(root)
    paths = iter_data_files(root)
    failures: list[ValidationIssue] = []

    for path in paths:
        relative_path = path.relative_to(root)
        try:
            validate_file(
                path,
                schema,
                allow_manual_golden_fixture=relative_path == GOLDEN_FIXTURE_PATH,
            )
        except ReportValidationError as error:
            failures.extend(
                ValidationIssue(f"{relative_path}:{issue.location}", issue.message)
                for issue in error.issues
            )

    if failures:
        raise ReportValidationError(failures)
    return paths


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate all Windows Patch Dashboard fixture and report JSON files."
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="repository root; defaults to the closest ancestor containing the schema",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for local development and CI."""

    arguments = _parser().parse_args(argv)
    try:
        root = arguments.root.resolve() if arguments.root is not None else find_repository_root()
        paths = validate_repository(root)
    except (FileNotFoundError, ReportValidationError) as error:
        print(error)
        return 1

    print(f"Validated {len(paths)} JSON file(s) against {SCHEMA_PATH}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
