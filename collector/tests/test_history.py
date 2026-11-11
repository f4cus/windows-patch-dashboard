from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from windows_patch_collector import cli
from windows_patch_collector.collector import collect_month
from windows_patch_collector.errors import CollectionConflictError, SourceParseError
from windows_patch_collector.history import load_historical_updates
from windows_patch_collector.http_client import MicrosoftHttpClient
from windows_patch_collector.models import StructuredResult, StructuredUpdate, SupportArticle
from windows_patch_collector.normalization import normalize_report
from windows_patch_collector.products import WINDOWS_SERVER_2012, WINDOWS_SERVER_2012_R2
from windows_patch_collector.validation import ReportValidationError, validate_document

STAMP = datetime(2026, 11, 10, 20, tzinfo=UTC)
URL = "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Nov"


@pytest.fixture
def prior_repository(tmp_path: Path, repository_root: Path) -> Path:
    for relative in ("data/schema/monthly-report.schema.json", "data/reports/2026-10.json"):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((repository_root / relative).read_bytes())
    return tmp_path


def _candidate() -> StructuredUpdate:
    return StructuredUpdate(
        "KB5126835",
        WINDOWS_SERVER_2012,
        date(2026, 11, 10),
        "security",
        URL,
        STAMP,
        "Security Update",
        release_date_explicit=False,
    )


def _structured(*updates: StructuredUpdate) -> StructuredResult:
    return StructuredResult(updates or (_candidate(),), URL, STAMP)


def test_loads_official_historical_facts_with_original_timestamps_and_hash(
    prior_repository,
) -> None:
    evidence = load_historical_updates(prior_repository, "2026-11")
    old = next(item for item in evidence if item.kb == "KB5126835")
    content = (prior_repository / "data/reports/2026-10.json").read_bytes()
    assert old.os == WINDOWS_SERVER_2012
    assert old.release_date == date(2026, 10, 13)
    assert old.report_path == "data/reports/2026-10.json"
    assert old.report_sha256 == hashlib.sha256(content).hexdigest()
    assert old.support_retrieved_at.isoformat() == "2026-10-14T23:00:08.033530+00:00"
    assert old.msrc_retrieved_at.isoformat() == "2026-10-14T23:00:00.768972+00:00"
    assert load_historical_updates(prior_repository, "2026-10") == ()
    assert load_historical_updates(prior_repository, "2026-09") == ()


@pytest.mark.parametrize(
    "change",
    ["partial", "missing-support", "missing-msrc", "foreign-host", "wrong-kb-url", "wrong-msrc"],
)
def test_unverified_or_unrelated_provenance_is_not_historical_evidence(prior_repository, change):
    path = prior_repository / "data/reports/2026-10.json"
    document = json.loads(path.read_bytes())
    row = next(row for row in document["updates"] if row["kb"] == "KB5126835")
    if change == "partial":
        document["status"] = "partial"
    elif change.startswith("missing-"):
        source_type = "microsoft-support" if change == "missing-support" else "msrc"
        row["sources"] = [s for s in row["sources"] if s["type"] != source_type]
    elif change == "wrong-msrc":
        row["sources"][0]["url"] = URL
    else:
        row["sources"][1]["url"] = (
            "https://example.com/help/5126835"
            if change == "foreign-host"
            else "https://support.microsoft.com/en-us/help/5999999"
        )
    path.write_text(json.dumps(document), encoding="utf-8")
    if change == "foreign-host":
        with pytest.raises(ReportValidationError):
            load_historical_updates(prior_repository, "2026-11")
        return
    assert all(e.kb != row["kb"] for e in load_historical_updates(prior_repository, "2026-11"))


def test_invalid_history_fails_closed(prior_repository):
    path = prior_repository / "data/reports/2026-10.json"
    document = json.loads(path.read_bytes())
    document["updates"][0]["releaseDate"] = "invalid"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ReportValidationError):
        load_historical_updates(prior_repository, "2026-11")


def test_misnamed_history_is_rejected(prior_repository):
    path = prior_repository / "data/reports/2026-10.json"
    path.rename(path.with_name("2026-09.json"))
    with pytest.raises(SourceParseError, match="month does not match"):
        load_historical_updates(prior_repository, "2026-11")


def test_fixtures_are_never_used_as_production_history(tmp_path, repository_root):
    path = tmp_path / "data/fixtures/2026-10.json"
    path.parent.mkdir(parents=True)
    path.write_bytes((repository_root / "data/reports/2026-10.json").read_bytes())
    assert load_historical_updates(tmp_path, "2026-11") == ()


def test_http_failure_can_exclude_only_verified_historical_candidates(prior_repository, schema):
    candidate = _candidate()
    evidence = load_historical_updates(prior_repository, "2026-11")
    result = normalize_report(
        month="2026-11",
        structured=_structured(candidate, replace(candidate, source_subtype="Monthly Rollup")),
        support_articles={},
        support_failures={candidate.kb: "HTTP 403"},
        historical_updates=evidence,
        generated_at=STAMP,
    )
    validate_document(result.document, schema)
    assert all(row["kb"] != candidate.kb for row in result.document["updates"])
    assert result.document["status"] == "partial"
    warning = next(w for w in result.warnings if "historical_report=" in w)
    assert "historical_report=data/reports/2026-10.json sha256=" in warning
    assert "Support release=2026-10-13" in warning
    assert "retrievedAt=2026-10-14T23:00:08.033530Z" in warning
    assert "live_support_error='HTTP 403'" in warning


@pytest.mark.parametrize("kind", ["explicit", "other-product", "oob", "current-month"])
def test_history_cannot_resolve_current_explicit_other_product_or_oob(prior_repository, kind):
    candidate = _candidate()
    evidence = load_historical_updates(prior_repository, "2026-11")
    if kind == "explicit":
        candidate = replace(candidate, release_date_explicit=True)
    elif kind == "other-product":
        candidate = replace(candidate, os=WINDOWS_SERVER_2012_R2)
    elif kind == "oob":
        candidate = replace(candidate, update_type="oob")
    else:
        evidence = tuple(replace(e, release_date=date(2026, 11, 10)) for e in evidence)
    result = normalize_report(
        month="2026-11",
        structured=_structured(candidate),
        support_articles={},
        support_failures={candidate.kb: "HTTP 403"},
        historical_updates=evidence,
        generated_at=STAMP,
    )
    assert result.document["status"] == "partial"
    assert any(row.get("publicationStatus") == "pending" for row in result.document["updates"])


@pytest.mark.parametrize("applicability", [None, (), (WINDOWS_SERVER_2012_R2,)])
def test_history_does_not_override_live_product_ambiguity(prior_repository, applicability):
    candidate = _candidate()
    article = SupportArticle(
        candidate.kb,
        date(2026, 10, 13),
        "https://support.microsoft.com/en-us/help/5126835",
        STAMP,
        "changes",
        "fixes",
        "known",
        "unknown",
        applies_to=applicability,
        package_kind="monthly-rollup",
    )
    with pytest.raises(CollectionConflictError):
        normalize_report(
            month="2026-11",
            structured=_structured(candidate),
            support_articles={article.kb: article},
            support_failures={},
            historical_updates=load_historical_updates(prior_repository, "2026-11"),
            generated_at=STAMP,
        )


@pytest.mark.parametrize("index_fails", [False, True])
def test_versioned_canonical_url_is_refetched_for_explicit_candidates(
    prior_repository,
    index_fails,
):
    evidence = load_historical_updates(prior_repository, "2026-11")
    old = next(e for e in evidence if e.kb == _candidate().kb)
    requested = []

    def handler(request):
        requested.append(str(request.url))
        if request.url.host == "learn.microsoft.com":
            return httpx.Response(403 if index_fails else 200, text="", request=request)
        if str(request.url) == old.support_url:
            return httpx.Response(
                200,
                request=request,
                text="""
                <h1>October 13, 2026 - KB5126835 (Monthly Rollup)</h1>
                <details id="supAppliesToList"><span class="appliesToItem">
                Windows Server 2012 ESU</span></details>""",
            )
        return httpx.Response(403, request=request)

    with (
        MicrosoftHttpClient(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(CollectionConflictError, match="Official date conflict"),
    ):
        collect_month(
            "2026-11",
            client=client,
            structured_fetcher=lambda _c, _m: _structured(
                replace(_candidate(), release_date_explicit=True)
            ),
            message_center_fetcher=lambda _c, _m: StructuredResult((), URL, STAMP),
            historical_updates=evidence,
            now=lambda: STAMP,
        )
    assert old.support_url in requested


def test_verified_historical_candidates_do_not_trigger_http_requests(prior_repository):
    def handler(request):
        pytest.fail(f"Historical candidate unexpectedly fetched {request.url}")

    with MicrosoftHttpClient(transport=httpx.MockTransport(handler)) as client:
        result = collect_month(
            "2026-11",
            client=client,
            structured_fetcher=lambda _c, _m: _structured(),
            message_center_fetcher=lambda _c, _m: StructuredResult((), URL, STAMP),
            historical_updates=load_historical_updates(prior_repository, "2026-11"),
            now=lambda: STAMP,
        )
    assert result.support_attempted == result.support_verified == 0
    assert any("live_support=not-requested" in w for w in result.normalized.warnings)


def test_unmatched_product_of_the_same_kb_still_requires_live_verification(prior_repository):
    candidate = _candidate()
    other_product = replace(candidate, os=WINDOWS_SERVER_2012_R2)
    requested = []

    def support_fetcher(_client, kb):
        requested.append(kb)
        return SupportArticle(
            kb,
            date(2026, 10, 13),
            "https://support.microsoft.com/en-us/help/5126835",
            STAMP,
            "changes",
            "fixes",
            "known",
            "none",
            applies_to=(WINDOWS_SERVER_2012,),
            package_kind="monthly-rollup",
        )

    with (
        MicrosoftHttpClient() as client,
        pytest.raises(CollectionConflictError, match="Official product conflict"),
    ):
        collect_month(
            "2026-11",
            client=client,
            structured_fetcher=lambda _c, _m: _structured(candidate, other_product),
            message_center_fetcher=lambda _c, _m: StructuredResult((), URL, STAMP),
            historical_updates=load_historical_updates(prior_repository, "2026-11"),
            support_fetcher=support_fetcher,
            now=lambda: STAMP,
        )
    assert requested == [candidate.kb]


def test_cli_uses_validated_history_without_rewriting_its_provenance(
    prior_repository,
    monkeypatch,
    capsys,
    schema,
):
    prior = prior_repository / "data/reports/2026-10.json"
    original = prior.read_bytes()

    def collect_with_sources(
        month, *, client, historical_updates, previous_report=None, support_history_fetcher=None
    ):
        return collect_month(
            month,
            client=client,
            structured_fetcher=lambda _c, _m: _structured(),
            message_center_fetcher=lambda _c, _m: StructuredResult((), URL, STAMP),
            historical_updates=historical_updates,
            now=lambda: STAMP,
        )

    monkeypatch.setattr(cli, "collect_month", collect_with_sources)
    monkeypatch.setattr(
        cli,
        "MicrosoftHttpClient",
        lambda: MicrosoftHttpClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(403, request=request))
        ),
    )
    assert cli.main(["collect", "--month", "2026-11", "--root", str(prior_repository)]) == 0
    document = json.loads((prior_repository / "data/reports/2026-11.json").read_bytes())
    validate_document(document, schema)
    assert prior.read_bytes() == original
    assert all(row["kb"] != _candidate().kb for row in document["updates"])
    assert "historical_report=data/reports/2026-10.json sha256=" in capsys.readouterr().out


def test_verified_hotpatch_metadata_is_excluded_before_monthly_conflict_resolution(schema):
    first = replace(_candidate(), kb="KB5999999")
    second = replace(first, supersedes="KB5888888")
    result = normalize_report(
        month="2026-11",
        structured=_structured(first, second),
        support_articles={},
        support_failures={},
        excluded_kbs=frozenset({first.kb}),
        generated_at=STAMP,
    )
    validate_document(result.document, schema)
    assert all(row["kb"] != first.kb for row in result.document["updates"])
    assert any("Support identifies it as hotpatch" in w for w in result.warnings)
