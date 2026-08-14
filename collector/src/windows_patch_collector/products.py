"""Explicit Microsoft product aliases for the supported V1 OS scope."""

from __future__ import annotations

import re
from collections.abc import Iterable

from windows_patch_collector.models import OsIdentity

WINDOWS_SERVER_2012 = OsIdentity("Windows Server", "2012", "ESU", "Windows Server 2012 (ESU)")
WINDOWS_SERVER_2012_R2 = OsIdentity(
    "Windows Server", "2012 R2", "ESU", "Windows Server 2012 R2 (ESU)"
)
WINDOWS_SERVER_2016 = OsIdentity("Windows Server", "2016", None, "Windows Server 2016")
WINDOWS_SERVER_2019 = OsIdentity("Windows Server", "2019", None, "Windows Server 2019")
WINDOWS_SERVER_2022 = OsIdentity("Windows Server", "2022", None, "Windows Server 2022")
WINDOWS_SERVER_23H2 = OsIdentity("Windows Server", "23H2", None, "Windows Server, version 23H2")
WINDOWS_SERVER_2025 = OsIdentity("Windows Server", "2025", None, "Windows Server 2025")

EXPECTED_SERVER_IDENTITIES = (
    WINDOWS_SERVER_2012,
    WINDOWS_SERVER_2012_R2,
    WINDOWS_SERVER_2016,
    WINDOWS_SERVER_2019,
    WINDOWS_SERVER_2022,
    WINDOWS_SERVER_2025,
)

_SERVER_ALIASES: tuple[tuple[re.Pattern[str], OsIdentity], ...] = (
    (
        re.compile(
            r"^Windows Server 2022, 23H2 Edition(?: \(Server Core installation\))?$",
            re.IGNORECASE,
        ),
        WINDOWS_SERVER_23H2,
    ),
    (
        re.compile(r"^Windows Server 2012 R2(?: \(Server Core installation\))?$", re.IGNORECASE),
        WINDOWS_SERVER_2012_R2,
    ),
    (
        re.compile(r"^Windows Server 2012(?: \(Server Core installation\))?$", re.IGNORECASE),
        WINDOWS_SERVER_2012,
    ),
    (
        re.compile(r"^Windows Server 2016(?: \(Server Core installation\))?$", re.IGNORECASE),
        WINDOWS_SERVER_2016,
    ),
    (
        re.compile(r"^Windows Server 2019(?: \(Server Core installation\))?$", re.IGNORECASE),
        WINDOWS_SERVER_2019,
    ),
    (
        re.compile(r"^Windows Server 2022(?: \(Server Core installation\))?$", re.IGNORECASE),
        WINDOWS_SERVER_2022,
    ),
    (
        re.compile(r"^Windows Server 2025(?: \(Server Core installation\))?$", re.IGNORECASE),
        WINDOWS_SERVER_2025,
    ),
)
_WINDOWS_11_ALIAS = re.compile(
    r"^Windows 11 [Vv]ersion (?P<version>[0-9]{2}H[12]) "
    r"for (?:x64|ARM64)-based Systems$"
)
_WINDOWS_11_VERSION = re.compile(r"^(?P<year>[0-9]{2})H(?P<half>[12])$")


def _collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def map_microsoft_product_name(name: str) -> OsIdentity | None:
    """Map an exact supported Microsoft product alias to the report identity."""

    normalized_name = _collapse_whitespace(name)
    for pattern, identity in _SERVER_ALIASES:
        if pattern.fullmatch(normalized_name) is not None:
            return identity

    windows_11_match = _WINDOWS_11_ALIAS.fullmatch(normalized_name)
    if windows_11_match is None:
        return None
    version = windows_11_match.group("version").upper()
    return OsIdentity("Windows 11", version, None, f"Windows 11 {version}")


def windows_11_branch_key(identity: OsIdentity) -> tuple[int, int]:
    """Return a deterministic branch order for a single Windows 11 identity."""

    match = _WINDOWS_11_VERSION.fullmatch(identity.version)
    if identity.family != "Windows 11" or match is None:
        raise ValueError(f"Not a single Windows 11 branch: {identity.display_name}")
    return int(match.group("year")), int(match.group("half"))


def combine_windows_11_identities(identities: Iterable[OsIdentity]) -> OsIdentity:
    """Combine architectures/branches sharing one verified Microsoft KB."""

    versions = sorted(
        {identity.version for identity in identities},
        key=lambda version: windows_11_branch_key(
            OsIdentity("Windows 11", version, None, f"Windows 11 {version}")
        ),
    )
    if not versions:
        raise ValueError("At least one Windows 11 identity is required")
    version = "/".join(versions)
    return OsIdentity("Windows 11", version, None, f"Windows 11 {version}")
