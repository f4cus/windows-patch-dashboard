"""Temporary live diagnostic for MSRC CVRF metadata conflict (fix branch only)."""

from __future__ import annotations

from collections import defaultdict
import xml.etree.ElementTree as ET

import httpx
import pytest

from windows_patch_collector.products import WINDOWS_SERVER_2012_R2, map_microsoft_product_name


def _name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _child(element: ET.Element, wanted: str) -> str | None:
    for child in element:
        if _name(child) == wanted and child.text:
            return child.text.strip()
    return None


def test_diagnose_live_msrc_2026_oct_kb5126836() -> None:
    url = "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Oct"
    response = httpx.get(url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    product_ids = {
        item.attrib["ProductID"]
        for item in root.iter()
        if _name(item) == "FullProductName"
        and "ProductID" in item.attrib
        and item.text
        and map_microsoft_product_name(item.text) == WINDOWS_SERVER_2012_R2
    }
    occurrences: dict[tuple[str, str, str], int] = defaultdict(int)
    for element in root.iter():
        if _name(element) != "Remediation":
            continue
        if (_child(element, "Description") or "").upper().removeprefix("KB") != "5126836":
            continue
        ids = {
            child.text.strip()
            for child in element.iter()
            if _name(child) == "ProductID" and child.text
        }
        if not ids.intersection(product_ids):
            continue
        key = (
            _child(element, "SubType") or "MISSING",
            _child(element, "Supercedence") or "MISSING",
            _child(element, "Date") or "MISSING",
        )
        occurrences[key] += 1

    summary = "\n".join(f"{count:4} x {key!r}" for key, count in sorted(occurrences.items()))
    pytest.fail(
        f"LIVE CVRF KB5126836 Windows Server 2012 R2; "
        f"product_ids={sorted(product_ids)!r}; variants:\n{summary}",
        pytrace=False,
    )
