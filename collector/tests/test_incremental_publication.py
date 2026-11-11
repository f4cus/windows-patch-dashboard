from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest

from windows_patch_collector.automation import ensure_refresh_publishable, semantic_report
from windows_patch_collector.collector import collect_month
from windows_patch_collector.errors import CollectionConflictError, SourceParseError
from windows_patch_collector.http_client import MicrosoftHttpClient
from windows_patch_collector.incremental import content_complete
from windows_patch_collector.lifecycle import ESU_EXPLANATION
from windows_patch_collector.models import StructuredResult, StructuredUpdate, SupportArticle
from windows_patch_collector.normalization import normalize_report
from windows_patch_collector.output import write_report_atomic
from windows_patch_collector.products import EXPECTED_SERVER_IDENTITIES, WINDOWS_SERVER_2012
from windows_patch_collector.validation import ReportValidationError, validate_document

STAMP = datetime(2026, 11, 10, 22, tzinfo=UTC)
URL = "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Nov"


def evidence():
    updates = tuple(
        StructuredUpdate(
            f"KB500000{index}",
            os,
            date(2026, 11, 10),
            "security",
            URL,
            STAMP,
            "Security Update",
            release_date_explicit=False,
        )
        for index, os in enumerate(EXPECTED_SERVER_IDENTITIES)
        if os.channel != "ESU"
    )
    articles = {
        u.kb: SupportArticle(
            u.kb,
            u.release_date,
            f"https://support.microsoft.com/en-us/help/{u.kb[2:]}",
            STAMP,
            "Verified changes.",
            "Verified fixes.",
            "No known issues.",
            "none",
            applies_to=(u.os,),
            package_kind="cumulative",
        )
        for u in updates
    }
    return StructuredResult(updates, URL, STAMP), articles


def normalize(structured, articles, *, failures=None, previous=None, stamp=STAMP):
    return normalize_report(
        month="2026-11",
        structured=structured,
        support_articles=articles,
        support_failures=failures or {},
        generated_at=stamp,
        previous_report=previous,
    )


def test_http_403_is_isolated_and_pending_is_not_no_publicado(schema):
    structured, articles = evidence()
    missing = structured.updates[0].kb

    def fetch(_client, kb):
        if kb == missing:
            from windows_patch_collector.errors import HttpFetchError

            raise HttpFetchError("HTTP 403")
        return articles[kb]

    with MicrosoftHttpClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(403))
    ) as client:
        result = collect_month(
            "2026-11",
            client=client,
            structured_fetcher=lambda _c, _m: structured,
            message_center_fetcher=lambda _c, _m: StructuredResult((), URL, STAMP),
            support_fetcher=fetch,
            now=lambda: STAMP,
        )
    doc = result.normalized.document
    validate_document(doc, schema)
    row = next(r for r in doc["updates"] if r["kb"] == missing)
    assert row["publicationStatus"] == "pending"
    assert row["releaseDate"] is None
    assert row["verification"]["status"] == "unavailable"
    assert row["verification"]["detail"] == "HTTP 403"
    assert len([r for r in doc["updates"] if r["publicationStatus"] == "verified"]) == 3


def test_verified_incomplete_content_can_be_enriched_without_timestamp_churn(schema):
    structured, articles = evidence()
    kb = structured.updates[0].kb
    partial = dict(articles)
    partial[kb] = replace(articles[kb], resolved_issues_summary="No disponible: pendiente.")
    first = normalize(structured, partial).document
    assert first["status"] == "partial"
    assert next(r for r in first["updates"] if r["kb"] == kb)["publicationStatus"] == "partial"
    complete = normalize(
        structured, articles, previous=first, stamp=STAMP + timedelta(days=1)
    ).document
    validate_document(complete, schema)
    assert complete["status"] == "generated"
    assert semantic_report(first) != semantic_report(complete)
    refreshed = normalize(
        structured, articles, previous=complete, stamp=STAMP + timedelta(days=2)
    ).document
    assert semantic_report(complete) == semantic_report(refreshed)


def test_pending_package_classification_preserves_the_support_verified_date(schema):
    structured, articles = evidence()
    kb = structured.updates[0].kb
    articles[kb] = replace(articles[kb], package_kind="unknown")
    report = normalize(structured, articles).document
    validate_document(report, schema)
    row = next(r for r in report["updates"] if r["kb"] == kb)
    assert row["publicationStatus"] == "pending"
    assert row["releaseDate"] == "2026-11-10"
    assert row["updateType"] == "unknown"
    assert row["changesSummary"] == "Verified changes."


def test_later_failures_preserve_confirmed_content_and_original_provenance(schema):
    structured, articles = evidence()
    baseline = normalize(structured, articles).document
    kb = structured.updates[0].kb
    unavailable = {k: v for k, v in articles.items() if k != kb}
    first = normalize(
        structured, unavailable, failures={kb: "HTTP 403"}, previous=baseline
    ).document
    second = normalize(
        structured,
        unavailable,
        failures={kb: "HTTP 403"},
        previous=first,
        stamp=STAMP + timedelta(days=1),
    ).document
    validate_document(second, schema)
    row = next(r for r in second["updates"] if r["kb"] == kb)
    assert content_complete(row)
    assert row["publicationStatus"] == "partial"
    assert any(
        s["type"] == "microsoft-support" and s["retrievedAt"] == "2026-11-10T22:00:00Z"
        for s in row["retainedSources"]
    )
    assert semantic_report(first) == semantic_report(second)


def test_retained_fields_keep_distinct_real_capture_times_without_timestamp_commits(schema):
    structured, articles = evidence()
    kb = structured.updates[0].kb
    first_articles = dict(articles)
    first_articles[kb] = replace(articles[kb], resolved_issues_summary="No disponible: pending.")
    first = normalize(structured, first_articles).document
    later_articles = dict(articles)
    later_articles[kb] = replace(
        articles[kb],
        changes_summary="No disponible: pending.",
        retrieved_at=STAMP + timedelta(hours=1),
    )
    second = normalize(structured, later_articles, previous=first).document
    unavailable = {k: v for k, v in articles.items() if k != kb}
    third = normalize(structured, unavailable, failures={kb: "HTTP 403"}, previous=second).document
    validate_document(third, schema)
    row = next(r for r in third["updates"] if r["kb"] == kb)
    assert {s["retrievedAt"] for s in row["retainedSources"]} == {
        "2026-11-10T22:00:00Z",
        "2026-11-10T23:00:00Z",
    }
    refreshed = normalize(
        structured,
        unavailable,
        failures={kb: "HTTP 403"},
        previous=third,
        stamp=STAMP + timedelta(days=1),
    ).document
    assert semantic_report(third) == semantic_report(refreshed)


def test_legacy_partial_baseline_does_not_upgrade_unconfirmed_package_metadata(schema):
    structured, articles = evidence()
    kb = structured.updates[0].kb
    legacy = normalize(structured, articles).document
    legacy["schemaVersion"] = "1.0.0"
    legacy["status"] = "partial"
    legacy["updates"] = [r for r in legacy["updates"] if r["kb"] != "NO PUBLICADO"]
    for row in legacy["updates"]:
        row.pop("publicationStatus")
        row.pop("verification")
    unavailable = {k: v for k, v in articles.items() if k != kb}
    result = normalize(structured, unavailable, previous=legacy).document
    validate_document(result, schema)
    row = next(r for r in result["updates"] if r["kb"] == kb)
    assert row["publicationStatus"] == "pending" and row["updateType"] == "unknown"
    assert row["changesSummary"] == "Verified changes."


def test_esu_ended_is_independent_of_report_completeness_and_known_issues(schema):
    structured, articles = evidence()
    doc = normalize(structured, articles).document
    validate_document(doc, schema)
    assert doc["status"] == "generated"
    rows = [r for r in doc["updates"] if r["os"]["channel"] == "ESU"]
    assert len(rows) == 2
    assert all(r["lifecycle"]["endedOn"] == "2026-10-13" for r in rows)
    assert all(r["changesSummary"] == ESU_EXPLANATION for r in rows)
    assert all(r["knownIssuesStatus"] == "unknown" and r["releaseDate"] is None for r in rows)
    assert all(any(s["type"] == "lifecycle" for s in r["sources"]) for r in rows)


def test_exceptional_post_esu_oob_is_retained_without_no_update_placeholder(schema):
    structured, articles = evidence()
    u = replace(
        structured.updates[0],
        kb="KB5999999",
        os=WINDOWS_SERVER_2012,
        release_date=date(2026, 11, 6),
        update_type="oob",
        release_date_explicit=True,
    )
    articles[u.kb] = replace(
        articles[structured.updates[0].kb],
        kb=u.kb,
        release_date=u.release_date,
        applies_to=(u.os,),
        package_kind="monthly-rollup",
        is_out_of_band=True,
    )
    result = normalize(replace(structured, updates=structured.updates + (u,)), articles).document
    validate_document(result, schema)
    rows = [r for r in result["updates"] if r["os"]["version"] == "2012"]
    assert len(rows) == 1 and rows[0]["kb"] == u.kb
    assert rows[0]["updateType"] == "oob" and rows[0]["lifecycle"]["status"] == "esu-ended"


def test_verified_unresolvable_monthly_conflict_remains_fatal():
    structured, articles = evidence()
    duplicate = replace(structured.updates[0], kb="KB5999999")
    articles[duplicate.kb] = replace(articles[structured.updates[0].kb], kb=duplicate.kb)
    with pytest.raises(CollectionConflictError, match="Multiple normal monthly KBs"):
        normalize(replace(structured, updates=structured.updates + (duplicate,)), articles)


def test_invalid_global_collection_and_invalid_output_preserve_previous_report(
    tmp_path, repository_root
):
    structured, articles = evidence()
    destination = tmp_path / "2026-11.json"
    write_report_atomic(
        normalize(structured, articles).document,
        repository_root=repository_root,
        destination=destination,
    )
    before = destination.read_bytes()

    def fail(_client, _month):
        raise SourceParseError("CVRF unavailable")

    with MicrosoftHttpClient() as client, pytest.raises(SourceParseError):
        collect_month("2026-11", client=client, structured_fetcher=fail)
    with pytest.raises(ReportValidationError):
        write_report_atomic({}, repository_root=repository_root, destination=destination)
    assert destination.read_bytes() == before


def test_incremental_publication_guard_accepts_pending_official_evidence_after_release(tmp_path):
    structured, _ = evidence()
    doc = normalize(structured, {}).document
    path = tmp_path / "2026-11.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    ensure_refresh_publishable(path, STAMP)
    with pytest.raises(ValueError, match="before 10:00 Pacific"):
        ensure_refresh_publishable(path, datetime(2026, 11, 10, 15, tzinfo=UTC))


def test_message_center_failure_preserves_confirmed_oob_and_other_kbs(schema):
    structured, articles = evidence()
    oob = replace(
        structured.updates[0],
        kb="KB5999999",
        update_type="oob",
        release_date=date(2026, 11, 12),
        release_date_explicit=True,
        supersedes=structured.updates[0].kb,
    )
    articles[oob.kb] = replace(
        articles[structured.updates[0].kb],
        kb=oob.kb,
        release_date=oob.release_date,
        is_out_of_band=True,
    )
    baseline = normalize(
        replace(structured, updates=structured.updates + (oob,)), articles
    ).document

    def failure(_client, _month):
        raise SourceParseError("message center unavailable")

    with MicrosoftHttpClient() as client:
        result = collect_month(
            "2026-11",
            client=client,
            structured_fetcher=lambda _c, _m: structured,
            message_center_fetcher=failure,
            support_fetcher=lambda _c, kb: articles[kb],
            previous_report=baseline,
            now=lambda: STAMP,
        )
    validate_document(result.normalized.document, schema)
    assert result.normalized.document["status"] == "partial"
    assert any(
        r["kb"] == oob.kb and r["updateType"] == "oob"
        for r in result.normalized.document["updates"]
    )
    assert any("OOB discovery unavailable" in w for w in result.normalized.warnings)


def test_historical_reports_keep_their_original_meaning(repository_root, schema):
    for month in ("2026-08", "2026-09", "2026-10"):
        path = repository_root / f"data/reports/{month}.json"
        report = json.loads(path.read_text("utf-8"))
        validate_document(report, schema)
        assert report["schemaVersion"] == "1.0.0"
        assert all("lifecycle" not in row for row in report["updates"])


@pytest.mark.parametrize("change", ["date", "product", "source", "report-status"])
def test_lifecycle_contract_rejects_invalid_facts_or_hidden_incompleteness(schema, change):
    structured, articles = evidence()
    doc = normalize(structured, articles).document
    row = next(r for r in doc["updates"] if "lifecycle" in r)
    if change == "date":
        row["lifecycle"]["endedOn"] = "2026-10-14"
    elif change == "product":
        doc["reportMonth"] = "2026-10"
    elif change == "source":
        row["sources"] = [s for s in row["sources"] if s["type"] != "lifecycle"]
    else:
        doc["updates"][-1]["publicationStatus"] = "pending"
    with pytest.raises(ReportValidationError):
        validate_document(doc, schema)
