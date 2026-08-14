"""Parser and fetcher for the official monthly MSRC CVRF document."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime

from windows_patch_collector.calendar import msrc_document_id, patch_tuesday
from windows_patch_collector.errors import SourceParseError
from windows_patch_collector.http_client import MicrosoftHttpClient
from windows_patch_collector.models import (
    OsIdentity,
    StructuredResult,
    StructuredUpdate,
    UpdateType,
)
from windows_patch_collector.products import (
    WINDOWS_SERVER_2012,
    WINDOWS_SERVER_2012_R2,
    combine_windows_11_identities,
    map_microsoft_product_name,
)

CVRF_ENDPOINT = "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/{document_id}"
_KB_PATTERN = re.compile(r"^(?:KB)?(?P<number>[0-9]{6,8})$", re.IGNORECASE)
_SUPPORTED_SECURITY_SUBTYPES = frozenset(
    {"security update", "monthly rollup", "security only", "security-only update"}
)


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if _local_name(child) == name and child.text:
            return " ".join(child.text.split())
    return None


def _descendant_text(element: ET.Element, name: str) -> str | None:
    for child in element.iter():
        if _local_name(child) == name and child.text:
            return " ".join(child.text.split())
    return None


def _parse_release_date(value: str) -> date:
    try:
        return date.fromisoformat(value[:10])
    except ValueError as error:
        raise SourceParseError(f"Invalid CVRF release date {value!r}") from error


def _kb(value: str | None) -> str | None:
    if value is None:
        return None
    match = _KB_PATTERN.fullmatch(value.strip())
    return f"KB{match.group('number')}" if match is not None else None


def _remediation_product_ids(remediation: ET.Element) -> set[str]:
    return {
        " ".join(element.text.split())
        for element in remediation.iter()
        if _local_name(element) == "ProductID" and element.text
    }


def parse_cvrf(
    content: bytes,
    *,
    month: str,
    source_url: str,
    retrieved_at: datetime,
) -> StructuredResult:
    """Parse supported KB/product relationships from an official CVRF document."""

    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        raise SourceParseError(f"Invalid CVRF XML from {source_url}: {error}") from error

    expected_document_id = msrc_document_id(month)
    document_id = _descendant_text(root, "ID")
    if document_id != expected_document_id:
        raise SourceParseError(
            f"CVRF document ID {document_id!r} does not match {expected_document_id!r}"
        )
    initial_release = _descendant_text(root, "InitialReleaseDate")
    if initial_release is None:
        raise SourceParseError("CVRF document lacks InitialReleaseDate")
    document_release = _parse_release_date(initial_release)
    expected_release = patch_tuesday(month)
    if document_release != expected_release:
        raise SourceParseError(
            f"CVRF release {document_release.isoformat()} does not match Patch Tuesday "
            f"{expected_release.isoformat()}"
        )

    products: dict[str, OsIdentity] = {}
    for element in root.iter():
        if _local_name(element) != "FullProductName" or not element.text:
            continue
        product_id = element.attrib.get("ProductID")
        identity = map_microsoft_product_name(element.text)
        if product_id and identity is not None:
            products[product_id] = identity

    candidates: dict[tuple[str, OsIdentity, date, UpdateType], tuple[str, str | None]] = {}
    warnings: list[str] = []
    for remediation in root.iter():
        if _local_name(remediation) != "Remediation":
            continue
        remediation_type = remediation.attrib.get("Type", "").casefold()
        if remediation_type not in {"vendor fix", "2"}:
            continue
        subtype = (_child_text(remediation, "SubType") or "").strip()
        normalized_subtype = subtype.casefold()
        is_oob = "out-of-band" in normalized_subtype or normalized_subtype == "oob"
        if "hotpatch" in normalized_subtype:
            continue
        if not is_oob and normalized_subtype not in _SUPPORTED_SECURITY_SUBTYPES:
            continue

        kb = _kb(_child_text(remediation, "Description"))
        if kb is None:
            continue
        identities = {
            products[value] for value in _remediation_product_ids(remediation) if value in products
        }
        if not identities:
            continue
        if (
            identities & {WINDOWS_SERVER_2012, WINDOWS_SERVER_2012_R2}
            and normalized_subtype != "monthly rollup"
        ):
            identities -= {WINDOWS_SERVER_2012, WINDOWS_SERVER_2012_R2}
        if not identities:
            continue

        date_text = _child_text(remediation, "Date")
        if is_oob and date_text is None:
            warnings.append(f"Ignored {kb} OOB candidate without an explicit remediation date")
            continue
        try:
            release_date = date.fromisoformat(date_text[:10]) if date_text else document_release
        except ValueError as error:
            raise SourceParseError(f"Invalid remediation date for {kb}: {date_text!r}") from error
        if not is_oob and release_date != expected_release:
            continue
        supersedes = _kb(_child_text(remediation, "Supercedence"))
        parsed_update_type: UpdateType = "oob" if is_oob else "security"
        for identity in identities:
            key = (kb, identity, release_date, parsed_update_type)
            existing = candidates.get(key)
            value = (subtype, supersedes)
            if existing is not None and existing != value:
                raise SourceParseError(f"Conflicting CVRF remediation metadata for {kb}")
            candidates[key] = value

    # Microsoft normally publishes one KB for multiple Windows 11 architectures and branches.
    server_candidates = {
        key: value for key, value in candidates.items() if key[1].family == "Windows Server"
    }
    windows_candidates: dict[
        tuple[str, date, UpdateType], list[tuple[OsIdentity, tuple[str, str | None]]]
    ] = defaultdict(list)
    for (kb, identity, release_date, update_type), value in candidates.items():
        if identity.family == "Windows 11":
            windows_candidates[(kb, release_date, update_type)].append((identity, value))

    updates: list[StructuredUpdate] = []
    for (kb, identity, release_date, update_type), (
        subtype,
        supersedes,
    ) in server_candidates.items():
        updates.append(
            StructuredUpdate(
                kb,
                identity,
                release_date,
                update_type,
                source_url,
                retrieved_at,
                subtype,
                supersedes=supersedes,
            )
        )
    for (kb, release_date, update_type), values in windows_candidates.items():
        metadata = {value for _, value in values}
        if len(metadata) != 1:
            raise SourceParseError(f"Conflicting Windows 11 CVRF metadata for {kb}")
        subtype, supersedes = metadata.pop()
        updates.append(
            StructuredUpdate(
                kb,
                combine_windows_11_identities(identity for identity, _ in values),
                release_date,
                update_type,
                source_url,
                retrieved_at,
                subtype,
                supersedes=supersedes,
            )
        )
    return StructuredResult(tuple(updates), source_url, retrieved_at, tuple(sorted(set(warnings))))


def fetch_cvrf(client: MicrosoftHttpClient, month: str) -> StructuredResult:
    """Fetch and parse one monthly CVRF document."""

    url = CVRF_ENDPOINT.format(document_id=msrc_document_id(month))
    response = client.get(url)
    return parse_cvrf(
        response.content,
        month=month,
        source_url=response.url,
        retrieved_at=response.retrieved_at,
    )
