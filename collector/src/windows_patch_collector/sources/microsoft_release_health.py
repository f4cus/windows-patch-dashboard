"""Discover explicitly announced OOB KBs from Microsoft's Windows message center."""

from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from bs4.element import Tag  # type: ignore[import-untyped]

from windows_patch_collector.errors import SourceParseError
from windows_patch_collector.http_client import MicrosoftHttpClient
from windows_patch_collector.models import OsIdentity, StructuredResult, StructuredUpdate
from windows_patch_collector.products import (
    WINDOWS_SERVER_23H2,
    WINDOWS_SERVER_2012,
    WINDOWS_SERVER_2012_R2,
    WINDOWS_SERVER_2016,
    WINDOWS_SERVER_2019,
    WINDOWS_SERVER_2022,
    WINDOWS_SERVER_2025,
    combine_windows_11_identities,
)

MESSAGE_CENTER_URL = (
    "https://learn.microsoft.com/en-us/windows/release-health/windows-message-center"
)
_KB = re.compile(r"\bKB[0-9]{6,8}\b", re.IGNORECASE)
_BRANCH = re.compile(r"\b[0-9]{2}H[12]\b", re.IGNORECASE)
_OOB = re.compile(r"\bout-of-band\b", re.IGNORECASE)
_SERVER_IDENTITIES = (
    ("Windows Server 2012 R2", WINDOWS_SERVER_2012_R2),
    ("Windows Server 2012", WINDOWS_SERVER_2012),
    ("Windows Server 2016", WINDOWS_SERVER_2016),
    ("Windows Server 2019", WINDOWS_SERVER_2019),
    ("Windows Server 2022", WINDOWS_SERVER_2022),
    ("Windows Server 2025", WINDOWS_SERVER_2025),
    ("Windows Server, version 23H2", WINDOWS_SERVER_23H2),
)


def _identity(label: str) -> OsIdentity | None:
    normalized = " ".join(label.split()).casefold()
    for name, identity in _SERVER_IDENTITIES:
        if name.casefold() in normalized:
            if identity == WINDOWS_SERVER_2012 and "windows server 2012 r2" in normalized:
                continue
            return identity
    if "windows 11" not in normalized:
        return None
    versions = {match.group().upper() for match in _BRANCH.finditer(label)}
    if not versions:
        return None
    return combine_windows_11_identities(
        OsIdentity("Windows 11", version, None, f"Windows 11 {version}") for version in versions
    )


def parse_message_center(
    content: bytes, *, month: str, source_url: str, retrieved_at: datetime
) -> StructuredResult:
    """Read dated OOB announcement rows and their OS-labelled Support KB links."""

    parsed_url = urlparse(source_url)
    if parsed_url.scheme != "https" or parsed_url.hostname != "learn.microsoft.com":
        raise SourceParseError(
            f"Windows message center resolved to a non-Microsoft URL: {source_url}"
        )
    soup = BeautifulSoup(content, "lxml")
    updates: dict[tuple[OsIdentity, str], StructuredUpdate] = {}
    warnings: list[str] = []
    for row in soup.select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 2:
            continue
        published_text = cells[1].get_text(" ", strip=True)
        if not published_text.startswith(month + "-"):
            continue
        headline = cells[0].find("b")
        if not isinstance(headline, Tag) or _OOB.search(headline.get_text(" ", strip=True)) is None:
            continue
        try:
            published = date.fromisoformat(published_text[:10])
        except ValueError as error:
            raise SourceParseError(f"Invalid OOB announcement date {published_text!r}") from error
        found = 0
        for item in cells[0].find_all("li"):
            label = item.get_text(" ", strip=True).split(":", 1)[0]
            identity = _identity(label)
            if identity is None:
                continue
            links = [
                link
                for link in item.find_all("a", href=True)
                if _KB.search(link.get_text(" ", strip=True)) is not None
            ]
            if len(links) != 1:
                raise SourceParseError(f"Ambiguous OOB KB link for {identity.display_name}")
            link = links[0]
            support_url = str(link["href"])
            support_host = urlparse(support_url)
            if support_host.scheme != "https" or support_host.hostname != "support.microsoft.com":
                raise SourceParseError(f"OOB announcement has a non-Support KB link: {support_url}")
            match = _KB.search(link.get_text(" ", strip=True))
            assert match is not None
            kb = match.group().upper()
            candidate = StructuredUpdate(
                kb,
                identity,
                published,
                "oob",
                source_url,
                retrieved_at,
                "Out-of-band announcement",
                support_url=support_url,
                source_type="release-health",
            )
            key = (identity, kb)
            if key in updates and updates[key] != candidate:
                raise SourceParseError(
                    f"Conflicting OOB announcements for {identity.display_name} {kb}"
                )
            updates[key] = candidate
            found += 1
        if not found:
            warnings.append(f"OOB announcement on {published.isoformat()} has no supported KB list")
    return StructuredResult(tuple(updates.values()), source_url, retrieved_at, tuple(warnings))


def fetch_message_center(client: MicrosoftHttpClient, month: str) -> StructuredResult:
    """Fetch Microsoft's official dated OOB announcement index."""

    response = client.get(MESSAGE_CENTER_URL)
    return parse_message_center(
        response.content,
        month=month,
        source_url=response.url,
        retrieved_at=response.retrieved_at,
    )
