"""Small typed boundary models between Microsoft sources and report normalization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

UpdateType = Literal["security", "oob"]
KnownIssuesStatus = Literal["none", "open", "resolved", "unknown"]
SupportLocale = Literal["es-ES", "en-US"]


@dataclass(frozen=True, slots=True, order=True)
class OsIdentity:
    """One normalized operating-system identity from the report contract."""

    family: Literal["Windows Server", "Windows 11"]
    version: str
    channel: str | None
    display_name: str

    def as_report_value(self) -> dict[str, str | None]:
        """Serialize the identity using the existing schema field names."""

        return {
            "family": self.family,
            "version": self.version,
            "channel": self.channel,
            "displayName": self.display_name,
        }


@dataclass(frozen=True, slots=True)
class StructuredUpdate:
    """A KB/product relationship verified by an MSRC structured source."""

    kb: str
    os: OsIdentity
    release_date: date
    update_type: UpdateType
    source_url: str
    retrieved_at: datetime
    source_subtype: str
    support_url: str | None = None
    supersedes: str | None = None


@dataclass(frozen=True, slots=True)
class StructuredResult:
    """Parsed output from one structured Microsoft document."""

    updates: tuple[StructuredUpdate, ...]
    source_url: str
    retrieved_at: datetime
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SupportArticle:
    """Deterministically extracted facts from one Microsoft Support article."""

    kb: str
    release_date: date
    source_url: str
    retrieved_at: datetime
    changes_summary: str
    resolved_issues_summary: str
    known_issues_summary: str
    known_issues_status: KnownIssuesStatus
    locale: SupportLocale = "en-US"
