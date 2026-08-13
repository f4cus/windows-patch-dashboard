"""Canonical, presentation-independent ordering for monthly update records."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any, TypeVar

CANONICAL_SERVER_ORDER = (
    "Windows Server 2012 (ESU)",
    "Windows Server 2012 R2 (ESU)",
    "Windows Server 2016",
    "Windows Server 2019",
    "Windows Server 2022",
    "Windows Server 2025",
)

_SERVER_RANK = {name: rank for rank, name in enumerate(CANONICAL_SERVER_ORDER)}
_WINDOWS_11_BRANCH = re.compile(r"(?P<year>[0-9]{2})H(?P<half>[12])")
_UNKNOWN_BRANCH = (999, 9)
_Update = TypeVar("_Update", bound=Mapping[str, Any])


def _windows_11_branch(version: object) -> tuple[int, int]:
    """Return the oldest branch represented by a Windows 11 version label."""

    if not isinstance(version, str):
        return _UNKNOWN_BRANCH

    branches = [
        (int(match.group("year")), int(match.group("half")))
        for match in _WINDOWS_11_BRANCH.finditer(version)
    ]
    return min(branches, default=_UNKNOWN_BRANCH)


def canonical_os_key(update: Mapping[str, Any]) -> tuple[int, int, int, str]:
    """Build the stable server-first OS key used by normalized report output."""

    os_value = update.get("os")
    if not isinstance(os_value, Mapping):
        return (2, 999, 9, "")

    family = os_value.get("family")
    display_name = os_value.get("displayName")
    normalized_name = display_name.casefold() if isinstance(display_name, str) else ""

    if family == "Windows Server":
        return (0, _SERVER_RANK.get(str(display_name), 999), 0, normalized_name)
    if family == "Windows 11":
        year, half = _windows_11_branch(os_value.get("version"))
        return (1, year, half, normalized_name)
    return (2, 999, 9, normalized_name)


def update_sort_key(update: Mapping[str, Any]) -> tuple[object, ...]:
    """Build a total ordering for records, including multiple updates for one OS."""

    release_date = update.get("releaseDate")
    update_type = update.get("updateType")
    kb = update.get("kb")
    return (
        *canonical_os_key(update),
        release_date if isinstance(release_date, str) else "",
        update_type if isinstance(update_type, str) else "",
        kb if isinstance(kb, str) else "",
    )


def sort_updates(updates: Iterable[_Update]) -> list[_Update]:
    """Return records in canonical report order without mutating the input."""

    return sorted(updates, key=update_sort_key)
