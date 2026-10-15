from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from windows_patch_collector import cli
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


@pytest.mark.parametrize(
    ("old", "new", "error"),
    [
        pytest.param(b"", b"", None, id="valid"),
        pytest.param(b"<h1", b"\xff<h1", "is not valid UTF-8", id="invalid-encoding"),
        pytest.param(b"<h1", b"<h2", "lacks an h1", id="missing-title"),
        pytest.param(b"KB5126835", b"KB5126836", "does not identify KB5126835", id="wrong-kb"),
        pytest.param(
            b"October 13, 2026",
            b"Unknown date",
            "lacks a recognizable release date",
            id="missing-date",
        ),
        pytest.param(
            b"October 13, 2026",
            b"October 14, 2026",
            "does not match Patch Tuesday",
            id="wrong-date",
        ),
        pytest.param(
            b"supAppliesToList",
            b"unrecognized",
            "Cannot verify ESU Monthly Rollup",
            id="missing-product",
        ),
        pytest.param(
            b"Windows Server 2012 ESU",
            b"Windows Server 2022, all editions",
            "Official product conflict",
            id="wrong-product",
        ),
        pytest.param(
            b"(Monthly Rollup)",
            b"",
            "Cannot classify ESU candidate",
            id="unknown-classification",
        ),
    ],
)
def test_collect_esu_keeps_only_valid_english_article_from_spanish_route(
    schema, old: bytes, new: bytes, error: str | None
) -> None:
    structured, _ = _evidence()
    update = next(u for u in structured.updates if u.kb == "KB5126835")
    structured = replace(structured, updates=(update,))
    captured = json.loads((FIXTURES / "microsoft-support-package-kinds.json").read_text("utf-8"))
    content = captured["articles"][update.kb]["html"].encode().replace(old, new)
    requested: list[str] = []
    spanish_url = f"https://support.microsoft.com/es-es/help/{update.kb.removeprefix('KB')}"
    english_url = spanish_url.replace("/es-es/", "/en-us/")

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host == "learn.microsoft.com":
            return httpx.Response(200, request=request, content=b"<html></html>")
        if str(request.url) == spanish_url:
            return httpx.Response(200, request=request, content=content)
        assert str(request.url) == english_url
        return httpx.Response(403, request=request)

    with MicrosoftHttpClient(transport=httpx.MockTransport(handler), now=lambda: STAMP) as client:
        if error is not None:
            with pytest.raises(CollectionConflictError, match=error):
                collect_month(
                    "2026-10",
                    client=client,
                    structured_fetcher=lambda _c, _m: structured,
                    message_center_fetcher=lambda _c, _m: StructuredResult((), URL, STAMP),
                    now=lambda: STAMP,
                )
        else:
            result = collect_month(
                "2026-10",
                client=client,
                structured_fetcher=lambda _c, _m: structured,
                message_center_fetcher=lambda _c, _m: StructuredResult((), URL, STAMP),
                now=lambda: STAMP,
            )

    assert requested[:2] == [spanish_url, english_url]
    assert len(requested) == 4  # Both official release indexes were consulted.
    if error is not None:
        return
    assert result.support_verified == result.support_attempted == 1
    report = result.normalized.document
    validate_document(report, schema)
    row = next(u for u in report["updates"] if u["kb"] == update.kb)
    assert row["os"]["version"] == "2012"
    assert row["releaseDate"] == "2026-10-13"
    assert row["sources"][-1] == {
        "type": "microsoft-support",
        "url": spanish_url,
        "retrievedAt": "2026-10-13T23:00:00Z",
    }


@pytest.mark.parametrize("missing", ["KB5126835", "KB5126836"])
def test_unverified_generic_esu_candidate_fails_instead_of_no_publicado(missing) -> None:
    structured, articles = _evidence()
    del articles[missing]
    with pytest.raises(CollectionConflictError, match="Cannot classify ESU candidate") as raised:
        normalize_report(
            month="2026-10",
            structured=structured,
            support_articles=articles,
            support_failures={missing: "unavailable"},
            generated_at=STAMP,
        )
    update = next(u for u in structured.updates if u.kb == missing)
    assert f"kb={missing}" in str(raised.value)
    assert f"os={update.os.display_name!r}" in str(raised.value)
    assert "msrc_subtype='Security Update'" in str(raised.value)
    assert "support_verification=failed support_error='unavailable'" in str(raised.value)


@pytest.mark.parametrize("kb", ["KB5126835", "KB5126836"])
@pytest.mark.parametrize("failure", ["http", "parse", "unknown-package"])
def test_esu_failure_diagnostics_reach_cli_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    kb: str,
    failure: str,
) -> None:
    structured, _ = _evidence()
    update = next(u for u in structured.updates if u.kb == kb)
    structured = replace(structured, updates=(update,))
    final = "https://support.microsoft.com/en-us/session/path-secret?token=secret#private"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "learn.microsoft.com":
            return httpx.Response(200, request=request, content=b"<html></html>")
        if "/help/" in request.url.path:
            return httpx.Response(302, request=request, headers={"Location": final})
        content = b"<html>sensitive-body</html>"
        if failure == "unknown-package":
            content = f"""<h1>October 13, 2026 - {kb}</h1>
            <details id="supAppliesToList"><span class="appliesToItem">
            Windows Server {update.os.version} ESU</span></details>""".encode()
        return httpx.Response(403 if failure == "http" else 200, request=request, content=content)

    def collect_with_mock_sources(month: str, *, client: MicrosoftHttpClient):
        return collect_month(
            month,
            client=client,
            structured_fetcher=lambda _c, _m: structured,
            message_center_fetcher=lambda _c, _m: StructuredResult((), URL, STAMP),
            now=lambda: STAMP,
        )

    monkeypatch.setattr(cli, "collect_month", collect_with_mock_sources)
    monkeypatch.setattr(
        cli,
        "MicrosoftHttpClient",
        lambda: MicrosoftHttpClient(transport=httpx.MockTransport(handler)),
    )

    assert cli.main(["collect", "--month", "2026-10", "--root", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert f"ERROR: Cannot classify ESU candidate {kb} as a Monthly Rollup" in output
    assert f"kb={kb} os={update.os.display_name!r}" in output
    assert "msrc_subtype='Security Update'" in output
    assert "https://support.microsoft.com/[redacted]" in output
    if failure == "unknown-package":
        assert "support_verification=parsed package_kind=unknown" in output
    else:
        assert "support_verification=failed" in output
        assert f"http_status={403 if failure == 'http' else 200}" in output
        assert f"/es-es/help/{kb.removeprefix('KB')}" in output
        assert f"/en-us/help/{kb.removeprefix('KB')}" in output
        reason = "HTTP 403" if failure == "http" else "lacks an h1"
        assert reason in output
    assert all(sensitive not in output for sensitive in ("secret", "private", "body", "<html>"))
    assert not (tmp_path / "data" / "reports" / "2026-10.json").exists()


@pytest.mark.parametrize("kb", ["KB5126835", "KB5126836"])
def test_esu_product_verification_failure_reports_parsed_package(kb: str) -> None:
    structured, articles = _evidence()
    articles[kb] = replace(articles[kb], applies_to=None)
    with pytest.raises(CollectionConflictError, match="Cannot verify ESU Monthly Rollup") as raised:
        normalize_report(
            month="2026-10",
            structured=structured,
            support_articles=articles,
            support_failures={},
            generated_at=STAMP,
        )
    assert f"kb={kb}" in str(raised.value)
    assert "msrc_subtype='Security Update'" in str(raised.value)
    assert "support_verification=parsed package_kind=monthly-rollup" in str(raised.value)
    assert "final_url='https://support.microsoft.com/en-us/servicing/os/[redacted]'" in str(
        raised.value
    )


@pytest.mark.parametrize("kb", ["KB5126835", "KB5126836"])
def test_explicit_msrc_rollup_with_support_failure_preserves_partial(kb: str) -> None:
    structured, articles = _evidence()
    structured = replace(
        structured,
        updates=tuple(
            replace(u, source_subtype="Monthly Rollup") if u.kb == kb else u
            for u in structured.updates
        ),
    )
    del articles[kb]
    result = normalize_report(
        month="2026-10",
        structured=structured,
        support_articles=articles,
        support_failures={kb: "HTTP 403"},
        generated_at=STAMP,
    )
    assert result.document["status"] == "partial"
    row = next(u for u in result.document["updates"] if u["kb"] == kb)
    assert row["knownIssuesStatus"] == "unknown"
    assert any(
        f"kb={kb}" in warning
        and "msrc_subtype='Monthly Rollup'" in warning
        and "support_verification=failed support_error='HTTP 403'" in warning
        for warning in result.warnings
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
