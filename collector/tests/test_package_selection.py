from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from windows_patch_collector.collector import collect_month
from windows_patch_collector.errors import CollectionConflictError
from windows_patch_collector.http_client import MicrosoftHttpClient
from windows_patch_collector.models import StructuredResult
from windows_patch_collector.normalization import normalize_report
from windows_patch_collector.sources.microsoft_support import parse_support_article
from windows_patch_collector.sources.msrc_cvrf import parse_cvrf
from windows_patch_collector.validation import validate_document

FIXTURES = Path(__file__).parent / "fixtures"
STAMP = datetime(2026, 10, 13, 23, tzinfo=UTC)
URL = "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Oct"


def _evidence():
    structured = parse_cvrf(
        (FIXTURES / "cvrf-2026-Oct-package-kinds.xml").read_bytes(),
        month="2026-10",
        source_url=URL,
        retrieved_at=STAMP,
    )
    captured = json.loads((FIXTURES / "microsoft-support-package-kinds.json").read_text("utf-8"))
    articles = {
        kb: parse_support_article(
            value["html"].encode(),
            expected_kb=kb,
            source_url=value["source_url"],
            retrieved_at=datetime.fromisoformat(value["retrieved_at"]),
        )
        for kb, value in captured["articles"].items()
    }
    return structured, articles


def test_october_esu_security_subtype_and_server_2016_ssu_regression(schema) -> None:
    structured, articles = _evidence()
    assert {u.kb for u in structured.updates} == set(articles)
    assert all(u.source_subtype == "Security Update" for u in structured.updates)
    assert {kb: a.package_kind for kb, a in articles.items()} == {
        "KB5126835": "monthly-rollup",
        "KB5126836": "monthly-rollup",
        "KB5126868": "cumulative",
        "KB5126649": "ssu",
    }
    with MicrosoftHttpClient() as client:
        result = collect_month(
            "2026-10",
            client=client,
            structured_fetcher=lambda _c, _m: structured,
            message_center_fetcher=lambda _c, _m: StructuredResult((), URL, STAMP),
            support_fetcher=lambda _c, kb: articles[kb],
            now=lambda: STAMP,
        )
    report = result.normalized.document
    validate_document(report, schema)
    assert {u["os"]["version"]: u["kb"] for u in report["updates"]} == {
        "2012": "KB5126835",
        "2012 R2": "KB5126836",
        "2016": "KB5126868",
    }
    assert all(u["releaseDate"] == "2026-10-13" for u in report["updates"])
    assert all(
        [s["type"] for s in u["sources"]] == ["msrc", "microsoft-support"]
        for u in report["updates"]
    )
    assert any("ignored ssu" in w for w in result.normalized.warnings)


@pytest.mark.parametrize("missing", ["KB5126835", "KB5126836"])
def test_unverified_generic_esu_candidate_fails_instead_of_no_publicado(missing) -> None:
    structured, articles = _evidence()
    del articles[missing]
    with pytest.raises(CollectionConflictError, match="Cannot classify ESU candidate"):
        normalize_report(
            month="2026-10",
            structured=structured,
            support_articles=articles,
            support_failures={missing: "unavailable"},
            generated_at=STAMP,
        )


def test_verified_unknown_package_cannot_win_monthly_conflict() -> None:
    structured, articles = _evidence()
    updates = tuple(u for u in structured.updates if u.os.version == "2016")
    articles = {"KB5126649": replace(articles["KB5126649"], package_kind="unknown")}
    with pytest.raises(CollectionConflictError, match="Multiple normal monthly KBs"):
        normalize_report(
            month="2026-10",
            structured=replace(structured, updates=updates),
            support_articles=articles,
            support_failures={},
            generated_at=STAMP,
        )


@pytest.mark.parametrize(
    ("title", "kind"),
    [
        ("KB5000000: Servicing stack update: October 13, 2026", "ssu"),
        ("13 de octubre de 2026: KB5000000 (paquete acumulativo mensual)", "monthly-rollup"),
        ("October 13, 2026 - KB5000000 (Security-only update)", "security-only"),
        ("October 13, 2026 - KB5000000 Cumulative Update for .NET Framework 4.8", "auxiliary"),
        ("October 13, 2026 - KB5000000 (OS Build 14393.9612) Preview", "auxiliary"),
        ("October 13, 2026 - KB5000000 (OS Build 14393.9612)", "cumulative"),
        ("October 13, 2026 - KB5000000", "unknown"),
    ],
)
def test_package_kind_uses_own_title_not_prerequisites(title, kind) -> None:
    article = parse_support_article(
        f"<h1>{title}</h1><p>Install the servicing stack update KB5999999 first.</p>".encode(),
        expected_kb="KB5000000",
        source_url="https://support.microsoft.com/en-us/test",
        retrieved_at=STAMP,
    )
    assert article.package_kind == kind


@pytest.mark.parametrize("kind", ["security-only", "auxiliary"])
def test_auxiliary_packages_do_not_conflict_with_lcu(kind) -> None:
    structured, articles = _evidence()
    updates = tuple(u for u in structured.updates if u.os.version == "2016")
    articles["KB5126649"] = replace(articles["KB5126649"], package_kind=kind)
    result = normalize_report(
        month="2026-10",
        structured=replace(structured, updates=updates),
        support_articles=articles,
        support_failures={},
        generated_at=STAMP,
    )
    assert [u["kb"] for u in result.document["updates"] if u["os"]["version"] == "2016"] == [
        "KB5126868"
    ]
