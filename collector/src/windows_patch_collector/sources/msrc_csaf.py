"""Parser for Microsoft's public CSAF advisory documents.

The V1 collector keeps this adapter tested and usable, while monthly discovery uses
CVRF because the CSAF distribution is one document per CVE rather than one monthly
manifest of KB/product relationships.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime
from typing import Any

from windows_patch_collector.calendar import patch_tuesday
from windows_patch_collector.errors import SourceParseError
from windows_patch_collector.models import (
    OsIdentity,
    StructuredResult,
    StructuredUpdate,
    UpdateType,
)
from windows_patch_collector.products import (
    combine_windows_11_identities,
    map_microsoft_product_name,
)

CSAF_ADVISORY_INDEX = "https://api.msrc.microsoft.com/csaf/advisories/index.txt"
_KB_IN_TEXT = re.compile(r"\bKB(?P<number>[0-9]{6,8})\b", re.IGNORECASE)
_KB_HELP_URL = re.compile(
    r"^https://support\.microsoft\.com/(?:[a-z]{2}-[a-z]{2}/)?help/(?P<number>[0-9]{6,8})(?:[/?#]|$)",
    re.IGNORECASE,
)
_SUPERSEDES = re.compile(r"\bsupersed(?:e|es|ed by)\s+KB?(?P<number>[0-9]{6,8})\b", re.IGNORECASE)


def _walk_product_branches(
    branches: object,
    result: dict[str, OsIdentity],
    inherited_identity: OsIdentity | None = None,
) -> None:
    if not isinstance(branches, list):
        return
    for branch in branches:
        if not isinstance(branch, dict):
            continue
        branch_name = branch.get("name")
        branch_identity = (
            map_microsoft_product_name(branch_name)
            if isinstance(branch_name, str) and branch.get("category") == "product_name"
            else None
        )
        identity = branch_identity or inherited_identity
        product = branch.get("product")
        if isinstance(product, dict):
            product_id = product.get("product_id")
            name = product.get("name")
            if isinstance(product_id, str) and isinstance(name, str):
                product_identity = map_microsoft_product_name(name) or identity
                if product_identity is not None:
                    result[product_id] = product_identity
        _walk_product_branches(branch.get("branches"), result, identity)


def _kb_from_remediation(remediation: dict[str, Any]) -> tuple[str, str | None] | None:
    url = remediation.get("url")
    if isinstance(url, str):
        match = _KB_HELP_URL.match(url)
        if match is not None:
            return f"KB{match.group('number')}", url
    details = remediation.get("details")
    if isinstance(details, str):
        match = _KB_IN_TEXT.search(details)
        if match is not None:
            return f"KB{match.group('number')}", None
    return None


def parse_csaf(
    content: bytes,
    *,
    month: str,
    source_url: str,
    retrieved_at: datetime,
) -> StructuredResult:
    """Parse verified supported remediations from one Microsoft CSAF advisory."""

    try:
        document = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceParseError(f"Invalid CSAF JSON from {source_url}: {error}") from error
    if not isinstance(document, dict):
        raise SourceParseError("CSAF document root must be an object")

    product_tree = document.get("product_tree")
    products: dict[str, OsIdentity] = {}
    if isinstance(product_tree, dict):
        _walk_product_branches(product_tree.get("branches"), products)
    if not products:
        raise SourceParseError("CSAF document contains no supported product identities")

    expected_release = patch_tuesday(month)
    grouped: dict[
        tuple[str, date, UpdateType],
        list[tuple[OsIdentity, str | None, str | None]],
    ] = defaultdict(list)
    vulnerabilities = document.get("vulnerabilities")
    if not isinstance(vulnerabilities, list):
        raise SourceParseError("CSAF document lacks a vulnerabilities array")
    for vulnerability in vulnerabilities:
        if not isinstance(vulnerability, dict):
            continue
        remediations = vulnerability.get("remediations")
        if not isinstance(remediations, list):
            continue
        for remediation_value in remediations:
            if (
                not isinstance(remediation_value, dict)
                or remediation_value.get("category") != "vendor_fix"
            ):
                continue
            kb_and_url = _kb_from_remediation(remediation_value)
            date_value = remediation_value.get("date")
            product_ids = remediation_value.get("product_ids")
            if (
                kb_and_url is None
                or not isinstance(date_value, str)
                or not isinstance(product_ids, list)
            ):
                continue
            try:
                release_date = date.fromisoformat(date_value[:10])
            except ValueError as error:
                raise SourceParseError(f"Invalid CSAF remediation date {date_value!r}") from error
            details = remediation_value.get("details")
            details_text = details if isinstance(details, str) else ""
            is_oob = "out-of-band" in details_text.casefold()
            if not is_oob and release_date != expected_release:
                continue
            if is_oob and release_date <= expected_release:
                continue
            kb, support_url = kb_and_url
            supersedes_match = _SUPERSEDES.search(details_text)
            supersedes = (
                f"KB{supersedes_match.group('number')}" if supersedes_match is not None else None
            )
            parsed_update_type: UpdateType = "oob" if is_oob else "security"
            for product_id in product_ids:
                if isinstance(product_id, str) and product_id in products:
                    grouped[(kb, release_date, parsed_update_type)].append(
                        (
                            products[product_id],
                            support_url,
                            supersedes,
                        )
                    )

    updates: list[StructuredUpdate] = []
    for (kb, release_date, update_type), values in grouped.items():
        identities = {value[0] for value in values}
        metadata = {(value[1], value[2]) for value in values}
        if len(metadata) != 1:
            raise SourceParseError(f"Conflicting CSAF remediation metadata for {kb}")
        support_url, supersedes = metadata.pop()
        subtype = "Out-of-band Vendor Fix" if update_type == "oob" else "Vendor Fix"
        server_identities = sorted(
            identity for identity in identities if identity.family == "Windows Server"
        )
        windows_identities = {
            identity for identity in identities if identity.family == "Windows 11"
        }
        output_identities = list(server_identities)
        if windows_identities:
            output_identities.append(combine_windows_11_identities(windows_identities))
        for identity in output_identities:
            updates.append(
                StructuredUpdate(
                    kb,
                    identity,
                    release_date,
                    update_type,
                    source_url,
                    retrieved_at,
                    subtype,
                    support_url=support_url,
                    supersedes=supersedes,
                )
            )
    return StructuredResult(tuple(updates), source_url, retrieved_at)
