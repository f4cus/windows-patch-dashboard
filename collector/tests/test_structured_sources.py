from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from windows_patch_collector.errors import SourceParseError
from windows_patch_collector.sources.msrc_csaf import parse_csaf
from windows_patch_collector.sources.msrc_cvrf import parse_cvrf

RETRIEVED = datetime(2026, 8, 13, 12, tzinfo=UTC)
CVRF_URL = "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Aug"
CSAF_URL = "https://api.msrc.microsoft.com/csaf/advisories/2026/msrc_cve-test.json"


def _remediation(kb: str, product: str, subtype: str = "Security Update") -> str:
    return f"""
    <Remediation Type="Vendor Fix">
      <Description>{kb}</Description><SubType>{subtype}</SubType>
      <Date>2026-08-11T07:00:00Z</Date><ProductID>{product}</ProductID>
    </Remediation>"""


def test_cvrf_parses_kbs_esu_and_combines_windows_branches() -> None:
    xml = f"""<Document>
      <DocumentTracking><Identification><ID>2026-Aug</ID></Identification>
        <InitialReleaseDate>2026-08-11T07:00:00Z</InitialReleaseDate></DocumentTracking>
      <ProductTree>
        <FullProductName ProductID="s12">Windows Server 2012</FullProductName>
        <FullProductName ProductID="s12r2">Windows Server 2012 R2</FullProductName>
        <FullProductName ProductID="w24">
          Windows 11 Version 24H2 for x64-based Systems
        </FullProductName>
        <FullProductName ProductID="w25">
          Windows 11 Version 25H2 for ARM64-based Systems
        </FullProductName>
      </ProductTree>
      <Vulnerability><Remediations>
        {_remediation("5120386", "s12", "Monthly Rollup")}
        {_remediation("5120385", "s12r2", "Monthly Rollup")}
        {_remediation("5121003", "w24")}{_remediation("5121003", "w25")}
      </Remediations></Vulnerability>
    </Document>"""
    parsed = parse_cvrf(xml.encode(), month="2026-08", source_url=CVRF_URL, retrieved_at=RETRIEVED)

    by_kb = {update.kb: update for update in parsed.updates}
    assert set(by_kb) == {"KB5120386", "KB5120385", "KB5121003"}
    assert by_kb["KB5120386"].os.channel == "ESU"
    assert by_kb["KB5120385"].os.version == "2012 R2"
    assert by_kb["KB5121003"].os.version == "24H2/25H2"


def test_cvrf_rejects_wrong_month_metadata() -> None:
    xml = b"""<Document><DocumentTracking><Identification><ID>2026-Jul</ID></Identification>
    <InitialReleaseDate>2026-07-14T07:00:00Z</InitialReleaseDate></DocumentTracking></Document>"""
    with pytest.raises(SourceParseError, match="does not match"):
        parse_cvrf(xml, month="2026-08", source_url=CVRF_URL, retrieved_at=RETRIEVED)


def test_csaf_parses_verified_kb_product_and_support_url() -> None:
    document = {
        "product_tree": {
            "branches": [
                {
                    "product": {
                        "product_id": "server-23h2",
                        "name": "Windows Server 2022, 23H2 Edition (Server Core installation)",
                    }
                }
            ]
        },
        "vulnerabilities": [
            {
                "remediations": [
                    {
                        "category": "vendor_fix",
                        "date": "2026-08-11T07:00:00Z",
                        "details": "Security Update KB5120999",
                        "product_ids": ["server-23h2"],
                        "url": "https://support.microsoft.com/help/5120999",
                    }
                ]
            }
        ],
    }
    parsed = parse_csaf(
        json.dumps(document).encode(),
        month="2026-08",
        source_url=CSAF_URL,
        retrieved_at=RETRIEVED,
    )
    assert len(parsed.updates) == 1
    assert parsed.updates[0].kb == "KB5120999"
    assert parsed.updates[0].os.display_name == "Windows Server, version 23H2"
    assert parsed.updates[0].support_url == "https://support.microsoft.com/help/5120999"


def test_csaf_does_not_guess_a_kb() -> None:
    document = {
        "product_tree": {
            "branches": [{"product": {"product_id": "s", "name": "Windows Server 2022"}}]
        },
        "vulnerabilities": [
            {
                "remediations": [
                    {
                        "category": "vendor_fix",
                        "date": "2026-08-11T07:00:00Z",
                        "details": "Security update",
                        "product_ids": ["s"],
                    }
                ]
            }
        ],
    }
    parsed = parse_csaf(
        json.dumps(document).encode(),
        month="2026-08",
        source_url=CSAF_URL,
        retrieved_at=RETRIEVED,
    )
    assert parsed.updates == ()
