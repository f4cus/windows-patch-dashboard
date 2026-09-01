"""Deterministic extraction from official Microsoft Support KB articles."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import cast
from urllib.parse import urlparse

from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from bs4.element import Tag  # type: ignore[import-untyped]

from windows_patch_collector.errors import (
    HttpFetchError,
    SourceParseError,
    UnsupportedHotpatchError,
)
from windows_patch_collector.http_client import MicrosoftHttpClient
from windows_patch_collector.models import KnownIssuesStatus, SupportArticle, SupportLocale

SUPPORT_HELP_URL = "https://support.microsoft.com/{locale}/help/{kb_number}"
_ENGLISH_DATE_PATTERN = re.compile(
    r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)\s+"
    r"(?P<day>[0-9]{1,2}),\s+(?P<year>[0-9]{4})",
    re.IGNORECASE,
)
_SPANISH_DATE_PATTERN = re.compile(
    r"(?P<day>[0-9]{1,2})\s+de\s+"
    r"(?P<month>enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|"
    r"noviembre|diciembre)\s+de\s+(?P<year>[0-9]{4})",
    re.IGNORECASE,
)
_ENGLISH_MONTHS = {
    name.casefold(): number
    for number, name in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        start=1,
    )
}
_SPANISH_MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        ),
        start=1,
    )
}
_NONE_PATTERNS = (
    "not currently aware of any issues",
    "currently not aware of any issues",
    "microsoft is not currently aware of any issues",
    "microsoft is not aware of any issues",
    "microsoft no tiene constancia actualmente de ningún problema",
    "microsoft no tiene constancia de ningún problema",
    "microsoft no tiene conocimiento actualmente de ningún problema",
    "microsoft no tiene conocimiento de ningún problema",
    "actualmente, microsoft no tiene conocimiento de ningún problema",
    "en este momento, microsoft no tiene conocimiento de ningún problema",
    "microsoft no está al tanto de ningún problema con respecto a esta actualización.",
    "por el momento no hemos identificado ningún problema con respecto a esta actualización.",
)
_RESOLVED_PATTERNS = (
    "resolved in",
    "issue is resolved",
    "this issue was resolved",
    "resolved by",
    "se resolvió en",
    "este problema se resolvió",
    "este problema se resuelve en",
    "este problema se ha resuelto",
    "este problema está resuelto",
    "problema resuelto en",
)
_OPEN_PATTERNS = (
    "after installing",
    "you might",
    "users might",
    "might fail",
    "may fail",
    "does not",
    "do not display",
    "unable to",
    "workaround",
    "después de instalar",
    "tras instalar",
    "es posible que",
    "puede que",
    "podría",
    "no muestra",
    "no se muestra",
    "no pueden",
    "solución alternativa",
)
_STRUCTURED_ITEM_PATTERN = re.compile(
    r"^\[(?P<label>[^\]\r\n]{1,80})\]\s+(?P<body>.+)$",
    re.DOTALL,
)
_EXPLICIT_FIX_PATTERNS = (
    re.compile(
        r"\bthis update (?:addresses|fixes|resolves) "
        r"(?:an?|the|this) (?:issue|problem)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\besta actualización (?:corrige|resuelve|soluciona) "
        r"(?:un|el|este) problema\b",
        re.IGNORECASE,
    ),
)
_GENERIC_SECURITY_UPDATE_PATTERNS = (
    re.compile(
        r"^this update provides security improvements\s*\."
        r"(?:\s*for more information (?:about|on) the security vulnerabilities "
        r"resolved by this update,\s*see the security update guide\s*\.?)?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^esta actualización proporciona mejoras de seguridad\s*\."
        r"(?:\s*para obtener más información (?:acerca de|sobre) las vulnerabilidades "
        r"de seguridad resueltas por esta actualización,\s*consulte la guía de "
        r"actualización de seguridad\s*\.?)?$",
        re.IGNORECASE,
    ),
)
_CONTENT_HEADINGS = frozenset(
    {
        "highlights",
        "improvements",
        "improvements and fixes",
        "summary",
        "aspectos destacados",
        "mejoras",
        "mejoras y correcciones",
        "resumen",
    }
)
_SPANISH_HEADINGS = frozenset(
    {"aspectos destacados", "mejoras", "mejoras y correcciones", "resumen"}
)
_SPANISH_KNOWN_HEADINGS = frozenset({"problemas conocidos en esta actualización"})
_KNOWN_HEADINGS = frozenset({"known issues in this update"}) | _SPANISH_KNOWN_HEADINGS
_UNAVAILABLE_CHANGES = (
    "No disponible: Microsoft Support no expuso cambios verificables en una sección compatible."
)
_UNAVAILABLE_RESOLVED = (
    "No disponible: Microsoft Support no documentó correcciones verificables en una "
    "sección compatible."
)
_UNAVAILABLE_KNOWN = (
    "No disponible: no se pudo verificar el estado de problemas conocidos en Microsoft Support."
)
_BOILERPLATE_PREFIXES = (
    "learn more about this cumulative security update",
    "the following is a summary",
    "the following summary outlines",
    "the bold text within",
    "for more information",
    "for information about the various types",
    "to view other notes",
    "if you've already installed previous updates",
    "obtenga más información sobre esta actualización de seguridad acumulativa",
    "a continuación se muestra un resumen",
    "el texto en negrita entre corchetes",
    "para obtener más información",
    "si ya instaló actualizaciones anteriores",
)


def _is_hidden(tag: Tag) -> bool:
    current: Tag | None = tag
    while current is not None:
        class_value = current.get("class")
        class_items = class_value if isinstance(class_value, list) else [class_value]
        classes = {str(value).casefold() for value in class_items if value is not None}
        style = str(current.get("style", "")).replace(" ", "").casefold()
        if (
            current.get("hidden") is not None
            or str(current.get("aria-hidden", "")).casefold() == "true"
            or "display:none" in style
            or "hidden" in classes
        ):
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def _heading_level(tag: Tag) -> int:
    return int(tag.name[1]) if tag.name and re.fullmatch(r"h[1-6]", tag.name) else 6


def _section_nodes(heading: Tag) -> list[Tag]:
    level = _heading_level(heading)
    result: list[Tag] = []
    for sibling in heading.next_siblings:
        if (
            isinstance(sibling, Tag)
            and sibling.name
            and re.fullmatch(r"h[1-6]", sibling.name)
            and _heading_level(sibling) <= level
        ):
            break
        if isinstance(sibling, Tag) and not _is_hidden(sibling):
            result.append(sibling)
    return result


def _meaningful_text(nodes: list[Tag]) -> list[str]:
    candidates: list[str] = []
    for node in nodes:
        details = [node] if node.name == "details" else node.select("details")
        rows = [row for row in node.select("tr") if row.select("td")]
        items = node.select("li")
        paragraphs = node.select("p")
        selected = (
            details
            or rows
            or items
            or paragraphs
            or ([node] if node.name in {"p", "div", "table", "details"} else [])
        )
        for item in selected:
            text = " ".join(item.get_text(" ", strip=True).split())
            normalized = text.casefold()
            if (
                len(text) >= 20
                and not normalized.startswith(_BOILERPLATE_PREFIXES)
                and normalized not in {value.casefold() for value in candidates}
            ):
                candidates.append(text)
    return candidates


def _structured_item_parts(value: str) -> tuple[str, str] | None:
    match = _STRUCTURED_ITEM_PATTERN.fullmatch(value)
    if match is None:
        return None
    return match.group("label"), match.group("body")


def _structured_text(nodes: list[Tag]) -> list[str]:
    candidates: list[str] = []
    normalized_candidates: set[str] = set()
    for node in nodes:
        if node.name in {"li", "tr"}:
            selected = [node]
        else:
            selected = [
                item
                for item in node.select("li, tr")
                if item.name != "tr" or bool(item.select("td"))
            ]
        for item in selected:
            if _is_hidden(item):
                continue
            text = " ".join(item.get_text(" ", strip=True).split())
            normalized = text.casefold()
            if _structured_item_parts(text) is not None and normalized not in normalized_candidates:
                candidates.append(text)
                normalized_candidates.add(normalized)
    return candidates


def _find_sections(soup: BeautifulSoup, names: frozenset[str]) -> list[list[str]]:
    sections: list[list[str]] = []
    for raw_heading in soup.find_all(re.compile(r"^h[1-6]$")):
        heading = cast(Tag, raw_heading)
        if _is_hidden(heading):
            continue
        title = " ".join(heading.get_text(" ", strip=True).split()).casefold()
        if title in names:
            text = _meaningful_text(_section_nodes(heading))
            if text:
                sections.append(text)
    return sections


def _find_structured_content(soup: BeautifulSoup) -> list[str]:
    candidates: list[str] = []
    normalized_candidates: set[str] = set()
    for raw_heading in soup.find_all(re.compile(r"^h[1-6]$")):
        heading = cast(Tag, raw_heading)
        if _is_hidden(heading):
            continue
        title = " ".join(heading.get_text(" ", strip=True).split()).casefold()
        if title not in _CONTENT_HEADINGS:
            continue
        section_nodes: list[Tag] = []
        for node in _section_nodes(heading):
            if node.name and re.fullmatch(r"h[1-6]", node.name):
                nested_title = " ".join(node.get_text(" ", strip=True).split()).casefold()
                if nested_title in _KNOWN_HEADINGS:
                    break
            section_nodes.append(node)
        for item in _structured_text(section_nodes):
            normalized = item.casefold()
            if normalized not in normalized_candidates:
                candidates.append(item)
                normalized_candidates.add(normalized)
    return candidates


def _parse_article_date(title: str) -> date:
    spanish_match = _SPANISH_DATE_PATTERN.search(title)
    if spanish_match is not None:
        return date(
            int(spanish_match.group("year")),
            _SPANISH_MONTHS[spanish_match.group("month").casefold()],
            int(spanish_match.group("day")),
        )

    english_match = _ENGLISH_DATE_PATTERN.search(title)
    if english_match is not None:
        return date(
            int(english_match.group("year")),
            _ENGLISH_MONTHS[english_match.group("month").casefold()],
            int(english_match.group("day")),
        )
    raise SourceParseError("Microsoft Support article title lacks a recognizable release date")


def _is_explicit_fix(value: str) -> bool:
    parts = _structured_item_parts(value)
    if parts is None:
        return False
    _, body = parts
    if body.casefold().startswith(("corregido:", "fixed:")):
        return True
    return any(pattern.search(body) is not None for pattern in _EXPLICIT_FIX_PATTERNS)


def _is_generic_security_update(value: str) -> bool:
    parts = _structured_item_parts(value)
    if parts is None:
        return False
    label, body = parts
    if label.casefold() not in {"actualizaciones de seguridad", "security updates"}:
        return False
    return any(pattern.fullmatch(body) is not None for pattern in _GENERIC_SECURITY_UPDATE_PATTERNS)


def _classify_known_issue_item(value: str) -> KnownIssuesStatus:
    normalized = value.casefold()
    if any(pattern in normalized for pattern in _RESOLVED_PATTERNS):
        return "resolved"
    if any(pattern in normalized for pattern in _OPEN_PATTERNS):
        return "open"
    if any(pattern in normalized for pattern in _NONE_PATTERNS):
        return "none"
    return "unknown"


def _aggregate_known_issue_status(items: list[str]) -> KnownIssuesStatus:
    states = {_classify_known_issue_item(item) for item in items}
    if "open" in states:
        return "open"
    if states == {"resolved"}:
        return "resolved"
    if states == {"none"}:
        return "none"
    return "unknown"


def _article_locale(soup: BeautifulSoup) -> SupportLocale:
    headings = {
        " ".join(cast(Tag, heading).get_text(" ", strip=True).split()).casefold()
        for heading in soup.find_all(re.compile(r"^h[1-6]$"))
        if isinstance(heading, Tag) and not _is_hidden(heading)
    }
    if headings & (_SPANISH_HEADINGS | _SPANISH_KNOWN_HEADINGS):
        return "es-ES"
    return "en-US"


def _assert_support_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "support.microsoft.com":
        raise SourceParseError(f"Support request resolved to a non-Microsoft URL: {url}")


def parse_support_article(
    content: bytes,
    *,
    expected_kb: str,
    source_url: str,
    retrieved_at: datetime,
) -> SupportArticle:
    """Extract article facts without interpreting absent markup as a clean state."""

    _assert_support_url(source_url)
    try:
        decoded_content = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SourceParseError("Microsoft Support article is not valid UTF-8") from error
    soup = BeautifulSoup(decoded_content, "lxml")
    h1_raw = soup.find("h1")
    if not isinstance(h1_raw, Tag):
        raise SourceParseError(f"Microsoft Support article for {expected_kb} lacks an h1")
    title = " ".join(h1_raw.get_text(" ", strip=True).split())
    if expected_kb.casefold() not in title.casefold():
        raise SourceParseError(f"Microsoft Support article title does not identify {expected_kb}")
    release_date = _parse_article_date(title)
    article_locale = _article_locale(soup)

    content_items = [
        item for item in _find_structured_content(soup) if not _is_generic_security_update(item)
    ]
    changes: list[str] = []
    fixes: list[str] = []
    for item in content_items:
        (fixes if _is_explicit_fix(item) else changes).append(item)
    changes_summary = " ".join(changes) if changes else _UNAVAILABLE_CHANGES
    resolved_summary = " ".join(fixes) if fixes else _UNAVAILABLE_RESOLVED

    known_sections = _find_sections(soup, _KNOWN_HEADINGS)
    known_items = list(dict.fromkeys(item for section in known_sections for item in section))
    if not known_items:
        known_status: KnownIssuesStatus = "unknown"
        known_summary = _UNAVAILABLE_KNOWN
    else:
        known_summary = " ".join(known_items)
        known_status = _aggregate_known_issue_status(known_items)

    return SupportArticle(
        expected_kb,
        release_date,
        source_url,
        retrieved_at,
        changes_summary,
        resolved_summary,
        known_summary,
        known_status,
        article_locale,
    )


def fetch_support_article(client: MicrosoftHttpClient, kb: str) -> SupportArticle:
    """Prefer verified Spanish content and fall back to the official English article."""

    if re.fullmatch(r"KB[0-9]{6,8}", kb) is None:
        raise ValueError(f"Invalid verified KB {kb!r}")

    try:
        spanish_article = _fetch_support_locale(client, kb, "es-es")
        if spanish_article.locale == "es-ES":
            return spanish_article
    except (HttpFetchError, SourceParseError):
        pass

    try:
        return _fetch_support_locale(client, kb, "en-us")
    except (HttpFetchError, SourceParseError) as error:
        raise SourceParseError(
            f"{kb} could not be verified in es-ES or en-US Microsoft Support"
        ) from error


def _fetch_support_locale(client: MicrosoftHttpClient, kb: str, locale: str) -> SupportArticle:
    response = client.get(SUPPORT_HELP_URL.format(locale=locale, kb_number=kb.removeprefix("KB")))
    if "/hotpatch/" in urlparse(response.url).path.casefold():
        raise UnsupportedHotpatchError(f"{kb} resolves to Microsoft's hotpatch publication path")
    return parse_support_article(
        response.content,
        expected_kb=kb,
        source_url=response.url,
        retrieved_at=response.retrieved_at,
    )
