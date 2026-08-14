"""Command-line interface for collection and repository validation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from windows_patch_collector.calendar import parse_report_month
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run collection, or retain no-argument repository validation compatibility."""

    arguments = _parser().parse_args(argv)
    try:
        root_value = getattr(arguments, "root", None)
        repository_root = root_value.resolve() if root_value is not None else find_repository_root()
        if arguments.command in {None, "validate"}:
            paths = validate_repository(repository_root)
            print(f"Validated {len(paths)} repository JSON file(s).")
            return 0

        month = str(arguments.month)
        destination = repository_root / "data" / "reports" / f"{month}.json"
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
