from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest

from windows_patch_collector.collector import collect_month
from windows_patch_collector.errors import CollectionConflictError
from windows_patch_collector.http_client import MicrosoftHttpClient
from windows_patch_collector.models import StructuredResult, StructuredUpdate, SupportArticle
from windows_patch_collector.products import WINDOWS_SERVER_2012
from windows_patch_collector.sources import support_history
from windows_patch_collector.sources.microsoft_support import parse_support_article
from windows_patch_collector.validation import validate_document

STAMP = datetime(2026, 11, 10, 22, tzinfo=UTC)
HISTORY_URL = "https://support.microsoft.com/es-es/servicing/os/test/kb5000000-history"
CVRF_URL = "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Nov"


def _html():
    return """<h1>13 de octubre de 2026 - KB5000000 (paquete acumulativo mensual)</h1>
    <details id="supAppliesToList"><span class="appliesToItem">
    Windows Server 2012 ESU</span></details>
    <div id="learnRenderLeftNav">
    <a class="learnRenderLeftNavLink" href="kb5000001-exception">
    06 de noviembre de 2026 - KB5000001 (acumulación mensual) fuera de banda</a>
    <a class="learnRenderLeftNavLink" href="kb5000002-ordinary">
    10 de noviembre de 2026 - KB5000002 (paquete acumulativo mensual)</a>
    <a class="learnRenderLeftNavLink" href="kb5000003-old">
    14 de octubre de 2026 - KB5000003 fuera de banda</a></div>
    <p><a href="kb5000004-body">06 de noviembre de 2026 - KB5000004 fuera de banda</a></p>"""


def test_dated_official_oob_navigation_can_discover_post_esu_exceptions(monkeypatch):
    monkeypatch.setattr(
        support_history,
        "ended_product_history_pages",
        lambda _month: ((WINDOWS_SERVER_2012, HISTORY_URL),),
    )
    with MicrosoftHttpClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text=_html(), request=request)
        ),
        now=lambda: STAMP,
    ) as client:
        result = support_history.fetch_post_esu_oob(client, "2026-11")
    assert len(result.updates) == 1
    update = result.updates[0]
    assert update.kb == "KB5000001" and update.release_date == date(2026, 11, 6)
    assert update.os == WINDOWS_SERVER_2012 and update.update_type == "oob"
    assert update.source_type == "microsoft-support" and update.source_url == HISTORY_URL
    assert (
        update.support_url
        == "https://support.microsoft.com/es-es/servicing/os/test/kb5000001-exception"
    )


@pytest.mark.parametrize("failure", ["403", "wrong-product", "missing-navigation"])
def test_history_failure_is_explicit_instead_of_fabricating_exception_or_absence(
    monkeypatch, failure
):
    monkeypatch.setattr(
        support_history,
        "ended_product_history_pages",
        lambda _month: ((WINDOWS_SERVER_2012, HISTORY_URL),),
    )
    content = _html()
    if failure == "wrong-product":
        content = content.replace("Windows Server 2012 ESU", "Windows Server 2022, all editions")
    elif failure == "missing-navigation":
        content = content.replace('id="learnRenderLeftNav"', 'id="unknown"')
    with MicrosoftHttpClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                403 if failure == "403" else 200, text=content, request=request
            )
        )
    ) as client:
        result = support_history.fetch_post_esu_oob(client, "2026-11")
    assert not result.updates
    assert any("exceptional OOB discovery unavailable" in warning for warning in result.warnings)


def test_exception_own_article_must_confirm_date_product_and_oob(monkeypatch, schema):
    monkeypatch.setattr(
        support_history,
        "ended_product_history_pages",
        lambda _month: ((WINDOWS_SERVER_2012, HISTORY_URL),),
    )
    with MicrosoftHttpClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, text=_html(), request=request)
        )
    ) as client:
        announcements = support_history.fetch_post_esu_oob(client, "2026-11")
        article = SupportArticle(
            "KB5000001",
            date(2026, 11, 6),
            announcements.updates[0].support_url,
            STAMP,
            "Verified changes.",
            "Verified fixes.",
            "No issues.",
            "none",
            is_out_of_band=True,
            applies_to=(WINDOWS_SERVER_2012,),
            package_kind="monthly-rollup",
        )
        result = collect_month(
            "2026-11",
            client=client,
            structured_fetcher=lambda _c, _m: StructuredResult((), CVRF_URL, STAMP),
            message_center_fetcher=lambda _c, _m: StructuredResult((), CVRF_URL, STAMP),
            support_history_fetcher=lambda _c, _m: announcements,
            support_fetcher=lambda _c, _kb: article,
            now=lambda: STAMP,
        )
        validate_document(result.normalized.document, schema)
        rows = [r for r in result.normalized.document["updates"] if r["os"]["version"] == "2012"]
        assert len(rows) == 1 and rows[0]["kb"] == article.kb
        assert rows[0]["lifecycle"]["status"] == "esu-ended"
        with pytest.raises(CollectionConflictError, match="does not confirm announced OOB"):
            collect_month(
                "2026-11",
                client=client,
                structured_fetcher=lambda _c, _m: StructuredResult((), CVRF_URL, STAMP),
                message_center_fetcher=lambda _c, _m: StructuredResult((), CVRF_URL, STAMP),
                support_history_fetcher=lambda _c, _m: announcements,
                support_fetcher=lambda _c, _kb: SupportArticle(
                    article.kb,
                    article.release_date,
                    article.source_url,
                    STAMP,
                    "changes",
                    "fixes",
                    "known",
                    "none",
                    applies_to=(WINDOWS_SERVER_2012,),
                    package_kind="monthly-rollup",
                ),
                now=lambda: STAMP,
            )


def test_spanish_monthly_rollup_variant_is_classified_from_its_title():
    article = parse_support_article(
        (
            "<h1>06 de noviembre de 2026 - KB5000001 (acumulación mensual) fuera de banda</h1>"
        ).encode(),
        expected_kb="KB5000001",
        source_url="https://support.microsoft.com/es-es/help/5000001",
        retrieved_at=STAMP,
    )
    assert article.package_kind == "monthly-rollup" and article.is_out_of_band


def test_explicit_history_metadata_enriches_undated_cvrf_without_inventing_msrc_dates(
    monkeypatch, schema
):
    monkeypatch.setattr(
        support_history,
        "ended_product_history_pages",
        lambda _month: ((WINDOWS_SERVER_2012, HISTORY_URL),),
    )

    def handler(request):
        return httpx.Response(
            200 if str(request.url) == HISTORY_URL else 403, text=_html(), request=request
        )

    with MicrosoftHttpClient(transport=httpx.MockTransport(handler)) as client:
        announcements = support_history.fetch_post_esu_oob(client, "2026-11")
        prior = StructuredUpdate(
            "KB5000001",
            WINDOWS_SERVER_2012,
            date(2026, 11, 10),
            "security",
            CVRF_URL,
            STAMP,
            "Security Update",
            release_date_explicit=False,
        )
        result = collect_month(
            "2026-11",
            client=client,
            structured_fetcher=lambda _c, _m: StructuredResult((prior,), CVRF_URL, STAMP),
            message_center_fetcher=lambda _c, _m: StructuredResult((), CVRF_URL, STAMP),
            support_history_fetcher=lambda _c, _m: announcements,
            now=lambda: STAMP,
        )
    validate_document(result.normalized.document, schema)
    row = next(r for r in result.normalized.document["updates"] if r["kb"] == prior.kb)
    assert row["publicationStatus"] == "partial"
    assert row["updateType"] == "oob" and row["releaseDate"] == "2026-11-06"
    assert {s["type"] for s in row["sources"]} >= {"msrc", "microsoft-support"}
    assert row["verification"]["status"] == "unavailable"


def test_conflicting_official_history_dates_are_not_silently_selected(monkeypatch):
    monkeypatch.setattr(
        support_history,
        "ended_product_history_pages",
        lambda _month: ((WINDOWS_SERVER_2012, HISTORY_URL),),
    )
    content = _html().replace(
        "</div>",
        """<a class="learnRenderLeftNavLink" href="kb5000001-exception">
    07 de noviembre de 2026 - KB5000001 (acumulación mensual) fuera de banda</a></div>""",
    )
    with (
        MicrosoftHttpClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, text=content, request=request)
            )
        ) as client,
        pytest.raises(CollectionConflictError, match="Conflicting official OOB history dates"),
    ):
        support_history.fetch_post_esu_oob(client, "2026-11")
