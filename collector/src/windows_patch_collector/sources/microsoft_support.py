"""Deterministic extraction from official Microsoft Support KB articles."""

from __future__ import annotations

import re
from collections.abc import Callable
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
from windows_patch_collector.models import (
    KnownIssuesStatus,
    OsIdentity,
    PackageKind,
    SupportArticle,
    SupportLocale,
)
from windows_patch_collector.products import map_microsoft_product_name

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
_OOB_TITLE_PATTERN = re.compile(r"\b(?:out-of-band|fuera de banda)\b", re.IGNORECASE)
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
    re.compile(
        r"\b(?:this|the) (?:issue|problem) (?:is|was|has been) "
        r"(?:(?:fully|completely) )?(?:resolved|fixed)\b"
    ),
    re.compile(r"(?:^|[.!?]\s+|\bresolution[:\s]+)resolved (?:in|by)\b"),
    re.compile(
        r"\b(?:este|el) problema (?:se (?:resolvió|resuelve|corrigió|solucionó|"
        r"ha (?:resuelto|corregido|solucionado))|está (?:resuelto|corregido|solucionado))\b"
    ),
    re.compile(r"(?:^|[.!?]\s+)problema resuelto en\b"),
)
# Explicit remaining symptoms override resolution evidence. Generic symptom prose can
# describe the history of a fully resolved issue, so it is checked separately below.
_PENDING_PATTERNS = (
    re.compile(r"\b(?:partially|partly) (?:resolved|fixed|addressed|mitigated)\b"),
    re.compile(r"\b(?:not|never) (?:(?:yet|fully|completely) )?(?:resolved|fixed|addressed)\b"),
    re.compile(r"\b(?:unresolved|remaining symptoms|symptoms not addressed yet)\b"),
    re.compile(r"\b(?:resolved|fixed) (?:only|for some|in some)\b"),
    re.compile(r"\b(?:not all symptoms|resolution is incomplete)\b"),
    re.compile(r"\b(?:symptoms?|issues?|problems?) (?:remain(?:s)?|persist(?:s)?|continue)\b"),
    re.compile(r"\b(?:is|are) still (?:affected|unable|unresolved|pending)\b"),
    re.compile(r"\bstill (?:experience|experiencing|fail|fails|failing|occur|occurs)\b"),
    re.compile(r"\bis working (?:to address|on (?:a |the )?(?:resolution|fix))\b"),
    re.compile(r"\b(?:resuelto|corregido|solucionado|mitigado) (?:parcialmente|en parte)\b"),
    re.compile(r"\bparcialmente (?:resuelto|corregido|solucionado|mitigado)\b"),
    re.compile(r"\b(?:no|aún no|todavía no) (?:se ha |está )?(?:resuelto|corregido)\b"),
    re.compile(r"\b(?:síntomas|problemas) (?:pendientes|persisten|continúan|siguen)\b"),
    re.compile(r"\b(?:siguen|continúan) (?:afectados|sin resolver|experimentando)\b"),
    re.compile(r"\b(?:está trabajando|trabaja) (?:para (?:resolver|solucionar)|en una solución)\b"),
)
_NO_PENDING_PATTERN = re.compile(
    r"\b(?:no remaining symptoms|no unresolved (?:symptoms|issues|problems)|"
    r"no (?:hay|quedan) (?:síntomas|problemas) pendientes)\b"
)
_UNCERTAIN_RESOLUTION_PATTERNS = (
    re.compile(
        r"\b(?:may|might|could|should|will|would|can) (?:be |have been )?"
        r"(?:(?:fully|completely) )?(?:resolved|fixed)\b"
    ),
    re.compile(r"\b(?:expected|scheduled|planned) to (?:be )?(?:resolved|fixed)\b"),
    re.compile(r"\b(?:podría|puede|debería) (?:estar |ser )?(?:resuelto|corregido)\b"),
    re.compile(r"\b(?:se resolverá|se espera que|debería resolverse)\b"),
    re.compile(r"\b(?:no confirmation|cannot confirm|not confirmed|unclear whether)\b"),
    re.compile(r"\b(?:no se ha confirmado|no hay confirmación|no está claro si)\b"),
)
_ACTIVE_SYMPTOM_PATTERN = re.compile(
    r"\b(?:users?|devices?|systems?) (?:cannot|are unable to)\b|"
    r"\b(?:might|may) (?:fail|experience|encounter)\b|"
    r"\b(?:usuarios?|dispositivos?|sistemas?) (?:no pueden|pueden experimentar)\b|"
    r"\bpodrían (?:experimentar|encontrar|fallar)\b|"
    r"\b(?:puede|podría) (?:fallar|producirse)\b"
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
    normalized = " ".join(value.casefold().split())
    pending_text = _NO_PENDING_PATTERN.sub("", normalized)
    if any(pattern.search(pending_text) for pattern in _PENDING_PATTERNS):
        return "open"
    if any(pattern.search(normalized) for pattern in _UNCERTAIN_RESOLUTION_PATTERNS):
        return "unknown"
    resolutions = [
        match for pattern in _RESOLVED_PATTERNS for match in pattern.finditer(normalized)
    ]
    confirms_none = any(pattern in normalized for pattern in _NONE_PATTERNS)
    if resolutions:
        if confirms_none:
            return "unknown"
        # A symptom description before the resolution is historical. Symptom
        # evidence after it can identify another issue in the same table row/details.
        after_resolution = normalized[max(match.end() for match in resolutions) :]
        if _ACTIVE_SYMPTOM_PATTERN.search(after_resolution):
            return "open"
        return "resolved"
    if any(pattern in normalized for pattern in _OPEN_PATTERNS):
        return "open"
    if confirms_none:
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


def _applies_to(soup: BeautifulSoup) -> tuple[OsIdentity, ...] | None:
    section = soup.select_one("#supAppliesToList")
    if section is None or _is_hidden(section):
        return None
    identities: set[OsIdentity] = set()
    for item in section.select(".appliesToItem"):
        if _is_hidden(item):
            continue
        label = " ".join(item.get_text(" ", strip=True).split())
        label = label.removesuffix(", all editions")
        if re.fullmatch(r"Windows Server 2012(?: R2)? ESU", label) is not None:
            label = label.removesuffix(" ESU")
        identity = map_microsoft_product_name(label)
        branch = re.fullmatch(r"Windows 11 version ([0-9]{2}H[12])", label, re.IGNORECASE)
        if branch is not None:
            version = branch.group(1).upper()
            identity = OsIdentity("Windows 11", version, None, f"Windows 11 {version}")
        if identity is not None:
            identities.add(identity)
    return tuple(sorted(identities))


def _package_kind(title: str) -> PackageKind:
    """Classify this article's package, never an SSU mentioned in the LCU body."""

    if re.search(r"servicing stack|pila de mantenimiento", title, re.IGNORECASE):
        return "ssu"
    if re.search(
        r"\.net|dynamic update|setup update|safe os|recovery environment|"
        r"licensing preparation|hotpatch|preview|vista previa",
        title,
        re.IGNORECASE,
    ):
        return "auxiliary"
    if re.search(r"security.only|solo de seguridad", title, re.IGNORECASE):
        return "security-only"
    if re.search(r"monthly rollup|paquete acumulativo mensual", title, re.IGNORECASE):
        return "monthly-rollup"
    if re.search(
        r"OS Builds?\s+[0-9]|compilaci[oó]n(?:es)? del (?:SO|sistema operativo)\s+[0-9]|"
        r"cumulative update|actualizaci[oó]n acumulativa",
        title,
        re.IGNORECASE,
    ):
        return "cumulative"
    return "unknown"


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
    if re.search(rf"\b{re.escape(expected_kb)}\b", title, re.IGNORECASE) is None:
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
        _OOB_TITLE_PATTERN.search(title) is not None,
        _applies_to(soup),
        _package_kind(title),
    )


def fetch_support_article(
    client: MicrosoftHttpClient,
    kb: str,
    *,
    fallback_urls: Callable[[], tuple[str, ...]] | None = None,
) -> SupportArticle:
    """Prefer verified Spanish content and fall back to the official English article."""

    if re.fullmatch(r"KB[0-9]{6,8}", kb) is None:
        raise ValueError(f"Invalid verified KB {kb!r}")

    errors: list[str] = []
    try:
        spanish_article = _fetch_support_locale(client, kb, "es-es")
        if spanish_article.locale == "es-ES":
            return spanish_article
    except (HttpFetchError, SourceParseError) as error:
        errors.append(str(error))

    try:
        return _fetch_support_locale(client, kb, "en-us")
    except (HttpFetchError, SourceParseError) as error:
        errors.append(str(error))

    if fallback_urls is not None:
        try:
            urls = fallback_urls()
        except (HttpFetchError, SourceParseError) as error:
            errors.append(str(error))
        else:
            # Prefer a Spanish link when the official index supplies one.
            for url in sorted(set(urls), key=lambda url: "/es-es/" not in url.casefold()):
                try:
                    return _fetch_support_url(client, kb, url)
                except (HttpFetchError, SourceParseError) as error:
                    errors.append(str(error))
    raise SourceParseError(
        f"{kb} could not be verified in es-ES or en-US Microsoft Support: " + "; ".join(errors)
    )


def _fetch_support_locale(client: MicrosoftHttpClient, kb: str, locale: str) -> SupportArticle:
    return _fetch_support_url(
        client, kb, SUPPORT_HELP_URL.format(locale=locale, kb_number=kb.removeprefix("KB"))
    )


def _fetch_support_url(client: MicrosoftHttpClient, kb: str, url: str) -> SupportArticle:
    _assert_support_url(url)
    response = client.get(url)
    _assert_support_url(response.url)
    if "/hotpatch/" in urlparse(response.url).path.casefold():
        raise UnsupportedHotpatchError(f"{kb} resolves to Microsoft's hotpatch publication path")
    return parse_support_article(
        response.content,
        expected_kb=kb,
        source_url=response.url,
        retrieved_at=response.retrieved_at,
    )
