from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from windows_patch_collector.errors import SourceParseError, UnsupportedHotpatchError
from windows_patch_collector.http_client import MicrosoftHttpClient
from windows_patch_collector.models import SupportArticle
from windows_patch_collector.sources.microsoft_support import (
    fetch_support_article,
    parse_support_article,
)

RETRIEVED = datetime(2026, 8, 13, 12, tzinfo=UTC)
URL = "https://support.microsoft.com/en-us/help/5120242/test-article"
SPANISH_URL = "https://support.microsoft.com/es-es/help/5120242/articulo"


def _article(known: str | None, content: str | None = None) -> bytes:
    known_section = (
        f"<h2>Known issues in this update</h2><div><p>{known}</p></div>" if known else ""
    )
    improvement = content or (
        "[Backup] This update addresses an issue in which scheduled backups could fail."
    )
    return f"""<html><body>
      <h1>August 11, 2026—KB5120242 (OS Build 20348.4294)</h1>
      <h2>Improvements</h2><div><ul><li>{improvement}</li></ul></div>
      {known_section}<h2>How to get this update</h2>
    </body></html>""".encode()


def _parse(content: bytes, *, source_url: str = URL) -> SupportArticle:
    return parse_support_article(
        content,
        expected_kb="KB5120242",
        source_url=source_url,
        retrieved_at=RETRIEVED,
    )


def _article_with_known_items(items: list[str]) -> bytes:
    details = "".join(
        f"<details><summary>Issue {index}</summary><p>{item}</p></details>"
        for index, item in enumerate(items, start=1)
    )
    return f"""<h1>August 11, 2026 - KB5120242</h1>
    <h2>Improvements</h2><p>This update improves reliability for managed devices.</p>
    <h2>Known issues in this update</h2>{details}
    <h2>How to get this update</h2>""".encode()


def test_routes_explicit_fix_exclusively_and_maps_no_known_issues() -> None:
    article = _parse(_article("Microsoft is not currently aware of any issues with this update."))
    assert article.changes_summary.startswith("No disponible")
    assert "scheduled backups" not in article.changes_summary
    assert "scheduled backups" in article.resolved_issues_summary
    assert article.known_issues_status == "none"


def test_spanish_structured_content_excludes_editorial_copy_and_generic_security() -> None:
    article = _parse(
        """<h1>11 de agosto de 2026: KB5120242</h1>
        <h2>Mejoras</h2>
        <p>Esta actualización de seguridad contiene correcciones y mejoras de calidad.</p>
        <ul><li>14 de julio de 2026: KB5099540</li></ul>
        <p>En el siguiente resumen se describen los principales problemas abordados.</p>
        <ul>
          <li>[Explorador de archivos] Esta actualización mejora las vistas previas DFS.</li>
          <li>[Sistema] Corregido: Esta actualización restaura la configuración esperada.</li>
          <li>[Actualizaciones de seguridad] Esta actualización proporciona mejoras de seguridad.
          Para obtener más información acerca de las vulnerabilidades de seguridad resueltas por
          esta actualización, consulte la Guía de actualización de seguridad.</li>
        </ul>
        <p>Si ya instaló actualizaciones anteriores, solo se descargarán las nuevas.</p>
        <p>Para obtener más información, consulte la documentación de Microsoft.</p>
        <h2>Problemas conocidos en esta actualización</h2>
        <p>Microsoft no está al tanto de ningún problema con respecto a esta actualización.</p>
        """.encode(),
        source_url=SPANISH_URL,
    )

    assert article.changes_summary == (
        "[Explorador de archivos] Esta actualización mejora las vistas previas DFS."
    )
    assert article.resolved_issues_summary == (
        "[Sistema] Corregido: Esta actualización restaura la configuración esperada."
    )
    assert "KB5099540" not in article.changes_summary
    assert "Actualizaciones de seguridad" not in article.changes_summary
    assert "Si ya instaló" not in article.changes_summary


def test_english_structured_content_excludes_editorial_copy_and_generic_security() -> None:
    article = _parse(
        b"""<h1>August 11, 2026 - KB5120242</h1>
        <h2>Improvements</h2>
        <p>This security update contains fixes and quality improvements.</p>
        <ul><li>July 14, 2026 - KB5099540</li></ul>
        <p>The following summary outlines the key issues addressed by this update.</p>
        <ul>
          <li>[File Explorer] This update improves previews on DFS mapped drives.</li>
          <li>[System] Fixed: This update restores the expected configuration.</li>
          <li>[Security updates] This update provides security improvements. For more information
          about the security vulnerabilities resolved by this update, see the Security Update
          Guide.</li>
        </ul>
        <p>If you've already installed previous updates, only the new updates will download.</p>
        <p>For more information, see Microsoft documentation.</p>
        <h2>Known issues in this update</h2>
        <p>Microsoft is not currently aware of any issues with this update.</p>"""
    )

    assert article.changes_summary == (
        "[File Explorer] This update improves previews on DFS mapped drives."
    )
    assert article.resolved_issues_summary == (
        "[System] Fixed: This update restores the expected configuration."
    )
    assert "KB5099540" not in article.changes_summary
    assert "Security updates" not in article.changes_summary
    assert "already installed" not in article.changes_summary


@pytest.mark.parametrize(
    ("heading", "item", "source_url"),
    [
        (
            "Mejoras",
            "[Copia de seguridad] Las copias programadas podrían fallar. "
            "Esta actualización resuelve el problema.",
            SPANISH_URL,
        ),
        (
            "Improvements",
            "[Backup] Scheduled backups might fail. This update resolves the issue.",
            URL,
        ),
    ],
)
def test_explicit_resolution_sentence_is_exclusively_a_fix(
    heading: str,
    item: str,
    source_url: str,
) -> None:
    article = _parse(
        f"""<h1>August 11, 2026 - KB5120242</h1>
        <h2>{heading}</h2><ul><li>{item}</li></ul>""".encode(),
        source_url=source_url,
    )

    assert article.changes_summary.startswith("No disponible")
    assert article.resolved_issues_summary == item


@pytest.mark.parametrize(
    ("heading", "item", "source_url"),
    [
        (
            "Mejoras",
            "[Seguridad] Esta actualización mejora la protección y restaura una opción.",
            SPANISH_URL,
        ),
        (
            "Improvements",
            "[Security] This update improves protection and restores an option.",
            URL,
        ),
        (
            "Mejoras",
            "[Actualizaciones de seguridad] Esta actualización proporciona mejoras de seguridad. "
            "También agrega una validación concreta para las firmas.",
            SPANISH_URL,
        ),
        (
            "Improvements",
            "[Security updates] This update provides security improvements. "
            "It also adds concrete signature validation.",
            URL,
        ),
    ],
)
def test_security_improves_and_restores_words_do_not_imply_a_fix(
    heading: str,
    item: str,
    source_url: str,
) -> None:
    article = _parse(
        f"""<h1>August 11, 2026 - KB5120242</h1>
        <h2>{heading}</h2><ul><li>{item}</li></ul>""".encode(),
        source_url=source_url,
    )

    assert article.changes_summary == item
    assert article.resolved_issues_summary.startswith("No disponible")


def test_unstructured_improvements_keep_unavailable_fallbacks() -> None:
    article = _parse(
        b"""<h1>August 11, 2026 - KB5120242</h1>
        <h2>Improvements</h2>
        <p>This update includes quality improvements from an earlier update.</p>
        <ul><li>July 14, 2026 - KB5099540</li></ul>
        <p>For more information, see Microsoft documentation.</p>"""
    )

    assert article.changes_summary.startswith("No disponible")
    assert article.resolved_issues_summary.startswith("No disponible")


def test_maps_open_known_issue() -> None:
    article = _parse(_article("After installing this update, WSUS does not display error details."))
    assert article.known_issues_status == "open"
    assert "WSUS" in article.known_issues_summary


def test_maps_open_known_issue_from_current_details_markup() -> None:
    content = b"""<h1>August 11, 2026 - KB5120242</h1>
    <h2>Improvements</h2><p>This update improves reliability for managed devices.</p>
    <h2>Known issues in this update</h2><details><summary>WSUS error details</summary>
    <p>After installing this update, WSUS does not display synchronization errors.</p></details>"""
    article = _parse(content)
    assert article.known_issues_status == "open"
    assert "WSUS error details" in article.known_issues_summary


def test_maps_explicitly_resolved_known_issue() -> None:
    article = _parse(_article("This issue was resolved in KB5120999."))
    assert article.known_issues_status == "resolved"


def test_one_resolved_and_one_open_known_issue_aggregates_to_open() -> None:
    article = _parse(
        _article_with_known_items(
            [
                "This issue was resolved in KB5120999.",
                "After installing this update, WSUS does not display synchronization errors.",
            ]
        )
    )
    assert article.known_issues_status == "open"


def test_all_verified_known_issues_resolved_aggregates_to_resolved() -> None:
    article = _parse(
        _article_with_known_items(
            [
                "This issue was resolved in KB5120998.",
                "This issue was resolved in KB5120999.",
            ]
        )
    )
    assert article.known_issues_status == "resolved"


def test_no_known_issues_does_not_override_a_separate_open_issue() -> None:
    article = _parse(
        _article_with_known_items(
            [
                "Microsoft is not currently aware of any issues with this update.",
                "After installing this update, WSUS does not display synchronization errors.",
            ]
        )
    )
    assert article.known_issues_status == "open"


def test_current_spanish_no_known_issues_does_not_override_an_open_issue() -> None:
    article = _parse(
        _article_with_known_items(
            [
                "Microsoft no está al tanto de ningún problema con respecto a esta actualización.",
                "Después de instalar esta actualización, WSUS no muestra los detalles del error.",
            ]
        )
    )
    assert article.known_issues_status == "open"


def test_contradictory_none_and_resolved_evidence_is_unknown() -> None:
    article = _parse(
        _article_with_known_items(
            [
                "Microsoft is not currently aware of any issues with this update.",
                "This issue was resolved in KB5120999.",
            ]
        )
    )
    assert article.known_issues_status == "unknown"


def test_missing_known_issue_section_is_unknown() -> None:
    article = _parse(_article(None))
    assert article.known_issues_status == "unknown"
    assert article.known_issues_summary.startswith("No disponible")


def test_markup_change_does_not_become_none() -> None:
    article = _parse(
        b"<h1>August 11, 2026 - KB5120242</h1><section data-new-layout='known'>No issues</section>"
    )
    assert article.known_issues_status == "unknown"


def test_rejects_wrong_or_missing_article_metadata() -> None:
    with pytest.raises(SourceParseError, match="does not identify"):
        _parse(b"<h1>August 11, 2026 - KB9999999</h1>")
    with pytest.raises(SourceParseError, match="lacks an h1"):
        _parse(b"<html><body>changed markup</body></html>")


def test_spanish_headings_release_date_and_explicit_no_known_issues() -> None:
    article = _parse(
        """<h1>11 de agosto de 2026: KB5120242 (compilación del SO 20348.5499)</h1>
        <h2>Mejoras y correcciones</h2>
        <ul><li>[Sistema] Corregido: Esta actualización corrige un problema de fiabilidad.</li></ul>
        <h2>Problemas conocidos en esta actualización</h2>
        <p>Microsoft no tiene conocimiento de ningún problema con esta actualización.</p>
        <h2>Cómo obtener esta actualización</h2>""".encode(),
        source_url=SPANISH_URL,
    )
    assert article.release_date.isoformat() == "2026-08-11"
    assert article.locale == "es-ES"
    assert article.changes_summary.startswith("No disponible")
    assert "Esta actualización corrige" in article.resolved_issues_summary
    assert article.known_issues_status == "none"


@pytest.mark.parametrize(
    "known_issue",
    [
        "Microsoft no está al tanto de ningún problema con respecto a esta actualización.",
        "Por el momento no hemos identificado ningún problema con respecto a esta actualización.",
    ],
)
def test_current_spanish_no_known_issue_phrases_map_to_none(known_issue: str) -> None:
    article = _parse(
        f"""<h1>11 de agosto de 2026: KB5120242</h1>
        <h2>Mejoras</h2><p>Esta actualización mejora la confiabilidad.</p>
        <h2>Problemas conocidos en esta actualización</h2>
        <p>{known_issue}</p>""".encode(),
        source_url=SPANISH_URL,
    )
    assert article.known_issues_status == "none"


def test_english_date_on_es_es_route_without_spanish_content_is_english() -> None:
    article = _parse(
        _article("Microsoft is not currently aware of any issues with this update."),
        source_url=SPANISH_URL,
    )
    assert article.locale == "en-US"


def test_spanish_heading_with_english_date_is_still_spanish_content() -> None:
    article = _parse(
        """<h1>August 11, 2026: KB5120242</h1>
        <h2>Mejoras</h2><p>Esta actualización mejora la confiabilidad.</p>
        <h2>Problemas conocidos en esta actualización</h2>
        <p>Microsoft no tiene constancia de ningún problema con esta actualización.</p>""".encode(),
        source_url=SPANISH_URL,
    )
    assert article.locale == "es-ES"
    assert article.known_issues_status == "none"


def test_spanish_summary_and_open_known_issue() -> None:
    article = _parse(
        """<h1>11 de agosto de 2026: KB5120242</h1>
        <h2>Resumen</h2>
        <ul><li>[Sistema] Esta actualización mejora la confiabilidad del sistema.</li></ul>
        <h2>Problemas conocidos en esta actualización</h2>
        <details><summary>Detalles de errores de WSUS</summary>
        <p>Después de instalar esta actualización, WSUS no muestra los detalles del error.</p>
        </details>""".encode(),
        source_url=SPANISH_URL,
    )
    assert "mejora la confiabilidad" in article.changes_summary
    assert article.known_issues_status == "open"


def test_fetch_prefers_spanish_and_uses_english_fallback_per_article() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path.startswith("/es-es/"):
            content = _article("Microsoft is not currently aware of any issues with this update.")
        else:
            content = _article("Microsoft is not currently aware of any issues with this update.")
        return httpx.Response(200, request=request, content=content)

    with MicrosoftHttpClient(transport=httpx.MockTransport(handler)) as client:
        article = fetch_support_article(client, "KB5120242")

    assert requested_paths == ["/es-es/help/5120242", "/en-us/help/5120242"]
    assert article.locale == "en-US"
    assert "/en-us/" in article.source_url


def test_fetch_stops_after_parseable_spanish_article() -> None:
    requested_paths: list[str] = []
    spanish = """<h1>11 de agosto de 2026: KB5120242</h1>
    <h2>Mejoras</h2><p>Esta actualización mejora la confiabilidad del sistema.</p>
    <h2>Problemas conocidos en esta actualización</h2>
    <p>Microsoft no tiene conocimiento de ningún problema con esta actualización.</p>""".encode()

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        return httpx.Response(200, request=request, content=spanish)

    with MicrosoftHttpClient(transport=httpx.MockTransport(handler)) as client:
        article = fetch_support_article(client, "KB5120242")

    assert requested_paths == ["/es-es/help/5120242"]
    assert article.locale == "es-ES"
    assert "/es-es/" in article.source_url


def test_official_hotpatch_redirect_is_excluded_before_article_parsing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/es-es/help/5123303":
            return httpx.Response(
                302,
                request=request,
                headers={
                    "Location": (
                        "https://support.microsoft.com/en-us/servicing/os/hotpatch/"
                        "windows-server-2022/2026/kb5123303"
                    )
                },
            )
        return httpx.Response(
            200,
            request=request,
            content=b"<h1>KB5123303: Security Update</h1>",
        )

    transport = httpx.MockTransport(handler)
    with (
        MicrosoftHttpClient(transport=transport) as client,
        pytest.raises(UnsupportedHotpatchError, match="hotpatch"),
    ):
        fetch_support_article(client, "KB5123303")
