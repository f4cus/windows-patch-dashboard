"""Command-line interface for collection and repository validation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from windows_patch_collector.automation import reconcile_generated_report, report_path
from windows_patch_collector.calendar import parse_report_month, resolve_report_month
from windows_patch_collector.collector import collect_month
from windows_patch_collector.errors import CollectorError
from windows_patch_collector.http_client import MicrosoftHttpClient
from windows_patch_collector.output import write_report_atomic
from windows_patch_collector.validation import (
    ReportValidationError,
    find_repository_root,
    validate_repository,
)


def _month(value: str) -> str:
    try:
        parse_report_month(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return value


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"Invalid date {value!r}; expected YYYY-MM-DD") from error


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect and validate Windows Patch Dashboard data."
    )
    subparsers = parser.add_subparsers(dest="command")
    collect = subparsers.add_parser("collect", help="collect one monthly report from Microsoft")
    collect.add_argument("--month", required=True, type=_month, help="report month in YYYY-MM form")
    collect.add_argument("--root", type=Path, help="repository root")
    validate = subparsers.add_parser("validate", help="validate repository report data")
    validate.add_argument("--root", type=Path, help="repository root")
    target = subparsers.add_parser(
        "target-month", help="resolve the latest eligible or explicitly requested report month"
    )
    target.add_argument("--month", type=_month, help="optional report month in YYYY-MM form")
    target.add_argument("--today", type=_date, help=argparse.SUPPRESS)
    reconcile = subparsers.add_parser(
        "reconcile-report", help="restore a report when only collection timestamps changed"
    )
    reconcile.add_argument(
        "--month", required=True, type=_month, help="report month in YYYY-MM form"
    )
    reconcile.add_argument(
        "--baseline", required=True, type=Path, help="pre-collection report copy"
    )
    reconcile.add_argument("--root", type=Path, help="repository root")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run collection, or retain no-argument repository validation compatibility."""

    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "target-month":
            today = arguments.today or datetime.now(UTC).date()
            print(resolve_report_month(today, arguments.month))
            return 0

        root_value = getattr(arguments, "root", None)
        repository_root = root_value.resolve() if root_value is not None else find_repository_root()
        if arguments.command in {None, "validate"}:
            paths = validate_repository(repository_root)
            print(f"Validated {len(paths)} repository JSON file(s).")
            return 0

        if arguments.command == "reconcile-report":
            destination = report_path(repository_root, str(arguments.month))
            changed = reconcile_generated_report(arguments.baseline.resolve(), destination)
            print(str(changed).lower())
            return 0

        month = str(arguments.month)
        destination = report_path(repository_root, month)
        print(f"Collecting Microsoft updates for {month}")
        with MicrosoftHttpClient() as client:
            result = collect_month(month, client=client)
        print("MSRC CVRF: OK")
        print(
            f"Support KBs: {result.support_verified} verified; "
            f"{result.hotpatch_excluded} hotpatch excluded"
        )
        for warning in result.normalized.warnings:
            print(f"WARNING: {warning}")
        write_report_atomic(
            result.normalized.document,
            repository_root=repository_root,
            destination=destination,
        )
        print("Report validation: OK")
        print(f"Written: {destination.relative_to(repository_root)}")
        return 0
    except (CollectorError, FileNotFoundError, OSError, ReportValidationError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1
