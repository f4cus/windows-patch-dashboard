from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from windows_patch_collector.errors import SourceParseError
from windows_patch_collector.models import SupportArticle
from windows_patch_collector.normalization import normalize_report
from windows_patch_collector.sources.microsoft_release_health import parse_message_center
from windows_patch_collector.sources.msrc_csaf import parse_csaf
from windows_patch_collector.sources.msrc_cvrf import parse_cvrf
from windows_patch_collector.validation import validate_document

RETRIEVED = datetime(2026, 8, 13, 12, tzinfo=UTC)
CVRF_URL = "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Aug"
CSAF_URL = "https://api.msrc.microsoft.com/csaf/advisories/2026/msrc_cve-test.json"
OCTOBER_CVRF_URL = "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Oct"
OCTOBER_RETRIEVED = datetime(2026, 10, 13, 22, tzinfo=UTC)
OCTOBER_FIXTURE = Path(__file__).parent / "fixtures" / "cvrf-2026-Oct-KB5127648.xml"


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


def test_cvrf_october_shared_kb_preserves_branch_supersedence(
    schema: dict[str, object],
) -> None:
    parsed = parse_cvrf(
        OCTOBER_FIXTURE.read_bytes(),
        month="2026-10",
        source_url=OCTOBER_CVRF_URL,
        retrieved_at=OCTOBER_RETRIEVED,
    )
    by_version = {update.os.version: update for update in parsed.updates}
    assert len(parsed.updates) == 2
    assert set(by_version) == {"24H2/25H2", "26H2"}
    assert by_version["24H2/25H2"].supersedes == "KB5124008"
    assert by_version["26H2"].supersedes is None
    assert all(update.kb == "KB5127648" for update in parsed.updates)
    assert all(update.update_type == "security" for update in parsed.updates)
    assert all(update.source_subtype == "Security Update" for update in parsed.updates)
    assert all(update.release_date == date(2026, 10, 13) for update in parsed.updates)
    assert all(not update.release_date_explicit for update in parsed.updates)

    # Synthetic Support content tests the report boundary without a live HTTP dependency.
    article = SupportArticle(
        "KB5127648",
        date(2026, 10, 13),
        "https://support.microsoft.com/help/5127648",
        OCTOBER_RETRIEVED,
        "Test changes.",
        "Test fixes.",
        "Test known issues unavailable.",
        "unknown",
    )
    normalized = normalize_report(
        month="2026-10",
        structured=parsed,
        support_articles={article.kb: article},
        support_failures={},
        generated_at=OCTOBER_RETRIEVED,
    )
    validate_document(normalized.document, schema)
    rows = [row for row in normalized.document["updates"] if row["kb"] == article.kb]
    assert [row["os"]["version"] for row in rows] == ["24H2/25H2", "26H2"]
    assert all(row["supersededBy"] is None for row in rows)
    assert all(
        [source["type"] for source in row["sources"]] == ["msrc", "microsoft-support"]
        for row in rows
    )


@pytest.mark.parametrize(
    "product",
    ["Windows Server 2012", "Windows Server 2012 R2"],
)
@pytest.mark.parametrize(
    "subtypes",
    [("Security Update", "Monthly Rollup"), ("Monthly Rollup", "Security Update")],
)
def test_cvrf_esu_prefers_rollup_when_duplicate_metadata_matches(
    product: str, subtypes: tuple[str, str]
) -> None:
    def remediation(subtype: str) -> str:
        return f"""<Remediation Type="Vendor Fix">
          <Description>5126836</Description>
          <SubType>{subtype}</SubType><Supercedence>5123066</Supercedence>
          <ProductID>esu</ProductID></Remediation>"""

    xml = f"""<Document>
      <DocumentTracking><Identification><ID>2026-Oct</ID></Identification>
        <InitialReleaseDate>2026-10-13T07:00:00Z</InitialReleaseDate>
      </DocumentTracking>
      <ProductTree><FullProductName ProductID="esu">{product}</FullProductName></ProductTree>
      <Vulnerability><Remediations>
        {remediation(subtypes[0])}{remediation(subtypes[1])}
      </Remediations></Vulnerability>
    </Document>"""
    parsed = parse_cvrf(
        xml.encode(),
        month="2026-10",
        source_url=OCTOBER_CVRF_URL,
        retrieved_at=OCTOBER_RETRIEVED,
    )
    assert len(parsed.updates) == 1
    assert parsed.updates[0].kb == "KB5126836"
    assert parsed.updates[0].os.display_name == f"{product} (ESU)"
    assert parsed.updates[0].source_subtype == "Monthly Rollup"
    assert parsed.updates[0].supersedes == "KB5123066"
    assert not parsed.updates[0].release_date_explicit
    assert parsed.warnings == ()


def test_cvrf_esu_keeps_rejecting_conflicting_supersedence() -> None:
    xml = b"""<Document>
      <DocumentTracking><Identification><ID>2026-Oct</ID></Identification>
        <InitialReleaseDate>2026-10-13T07:00:00Z</InitialReleaseDate>
      </DocumentTracking>
      <ProductTree>
        <FullProductName ProductID="esu">Windows Server 2012 R2</FullProductName>
      </ProductTree>
      <Vulnerability><Remediations>
        <Remediation Type="Vendor Fix"><Description>5126836</Description>
          <SubType>Monthly Rollup</SubType><Supercedence>5123066</Supercedence>
          <ProductID>esu</ProductID></Remediation>
        <Remediation Type="Vendor Fix"><Description>5126836</Description>
          <SubType>Security Update</SubType><Supercedence>5120000</Supercedence>
          <ProductID>esu</ProductID></Remediation>
      </Remediations></Vulnerability>
    </Document>"""
    with pytest.raises(SourceParseError, match="Conflicting CVRF remediation metadata"):
        parse_cvrf(
            xml,
            month="2026-10",
            source_url=OCTOBER_CVRF_URL,
            retrieved_at=OCTOBER_RETRIEVED,
        )


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        (b"<ns2:Supercedence>5124008</ns2:Supercedence>", b""),
        (
            b"<ns2:SubType>Security Update</ns2:SubType>",
            b"<ns2:SubType>Monthly Rollup</ns2:SubType>",
        ),
    ],
)
def test_cvrf_still_rejects_conflicting_metadata_within_one_branch(
    original: bytes,
    replacement: bytes,
) -> None:
    # The fixture repeats the 24H2 products across vulnerability remediations.
    content = OCTOBER_FIXTURE.read_bytes().replace(original, replacement, 1)
    with pytest.raises(SourceParseError, match="Conflicting CVRF remediation metadata"):
        parse_cvrf(
            content,
            month="2026-10",
            source_url=OCTOBER_CVRF_URL,
            retrieved_at=OCTOBER_RETRIEVED,
        )


def test_cvrf_keeps_oob_branch_metadata_separate() -> None:
    content = OCTOBER_FIXTURE.read_bytes().replace(
        b"<ns2:SubType>Security Update</ns2:SubType>",
        b"<ns2:SubType>Out-of-band Security Update</ns2:SubType>"
        b"<ns2:Date>2026-10-15T07:00:00Z</ns2:Date>",
    )
    parsed = parse_cvrf(
        content,
        month="2026-10",
        source_url=OCTOBER_CVRF_URL,
        retrieved_at=OCTOBER_RETRIEVED,
    )
    assert len(parsed.updates) == 2
    assert {update.os.version: update.supersedes for update in parsed.updates} == {
        "24H2/25H2": "KB5124008",
        "26H2": None,
    }
    assert all(update.update_type == "oob" for update in parsed.updates)
    assert all(update.release_date == date(2026, 10, 15) for update in parsed.updates)
    assert all(update.release_date_explicit for update in parsed.updates)


def test_cvrf_keeps_implicit_remediation_date_and_explicit_supersedence() -> None:
    xml = b"""<Document><DocumentTracking><Identification><ID>2026-Aug</ID></Identification>
      <InitialReleaseDate>2026-08-11T07:00:00Z</InitialReleaseDate></DocumentTracking>
      <ProductTree><FullProductName ProductID="w">Windows 11 Version 24H2 for x64-based Systems
      </FullProductName></ProductTree><Vulnerability><Remediations>
      <Remediation Type="Vendor Fix"><Description>5120242</Description>
      <SubType>Security Update</SubType><Supercedence>5120000</Supercedence>
      <ProductID>w</ProductID></Remediation></Remediations></Vulnerability></Document>"""
    parsed = parse_cvrf(xml, month="2026-08", source_url=CVRF_URL, retrieved_at=RETRIEVED)
    assert len(parsed.updates) == 1
    assert parsed.updates[0].release_date.isoformat() == "2026-08-11"
    assert parsed.updates[0].release_date_explicit is False
    assert parsed.updates[0].supersedes == "KB5120000"


def test_message_center_discovers_dated_oob_for_supported_os_only() -> None:
    html = b"""<table><tr><td><b>Out-of-band updates released</b>
    <ul>
      <li>Windows 11, versions 25H2 and 24H2: <a href="https://support.microsoft.com/help/5120999">KB5120999</a></li>
      <li>Windows Server 2012 R2: <a href="https://support.microsoft.com/help/5120998">KB5120998</a></li>
      <li>Windows 10, version 22H2: <a href="https://support.microsoft.com/help/5120997">KB5120997</a></li>
    </ul></td><td>2026-08-15<br>10:00 PT</td></tr></table>"""
    parsed = parse_message_center(
        html,
        month="2026-08",
        source_url="https://learn.microsoft.com/en-us/windows/release-health/windows-message-center",
        retrieved_at=RETRIEVED,
    )
    assert {update.kb for update in parsed.updates} == {"KB5120999", "KB5120998"}
    assert {update.os.display_name for update in parsed.updates} == {
        "Windows 11 24H2/25H2",
        "Windows Server 2012 R2 (ESU)",
    }
    assert all(update.update_type == "oob" for update in parsed.updates)
    assert all(update.release_date.isoformat() == "2026-08-15" for update in parsed.updates)
    assert all(update.source_type == "release-health" for update in parsed.updates)


def test_message_center_ignores_monthly_links_outside_oob_announcements() -> None:
    html = b"""<table><tr><td><b>September security update is available</b>
    <ul><li>Windows Server 2022: <a href="https://support.microsoft.com/help/5120999">KB5120999</a></li></ul>
    </td><td>2026-08-11</td></tr></table>"""
    parsed = parse_message_center(
        html,
        month="2026-08",
        source_url="https://learn.microsoft.com/en-us/windows/release-health/windows-message-center",
        retrieved_at=RETRIEVED,
    )
    assert parsed.updates == ()


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
