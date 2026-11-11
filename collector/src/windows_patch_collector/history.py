"""Read conservative historical evidence from validated production reports."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit

from windows_patch_collector.calendar import msrc_document_id, parse_report_month
from windows_patch_collector.errors import SourceParseError
from windows_patch_collector.models import HistoricalUpdate, OsIdentity, StructuredUpdate
from windows_patch_collector.validation import load_schema, validate_document


def historical_match(
    update: StructuredUpdate,
    month: str,
    evidence: Mapping[tuple[OsIdentity, str], HistoricalUpdate],
) -> HistoricalUpdate | None:
    """Match only undated monthly MSRC candidates to an exact older KB/OS pair."""

    prior = evidence.get((update.os, update.kb))
    if (
        prior is not None
        and not update.release_date_explicit
        and update.update_type == "security"
        and update.source_type == "msrc"
        and prior.release_date.strftime("%Y-%m") < month
    ):
        return prior
    return None


def load_historical_updates(repository_root: Path, month: str) -> tuple[HistoricalUpdate, ...]:
    """Load prior production facts with dual official provenance; never read fixtures."""

    parse_report_month(month)
    paths = sorted(
        path
        for path in (repository_root / "data/reports").glob("*.json")
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}", path.stem) and path.stem < month
    )
    if not paths:
        return ()
    schema = load_schema(repository_root)
    evidence: list[HistoricalUpdate] = []
    for path in paths:
        content = path.read_bytes()
        document = json.loads(content)
        if not isinstance(document, dict):
            raise SourceParseError(f"Historical report {path.name} must be an object")
        validate_document(document, schema)
        if document["reportMonth"] != path.stem:
            raise SourceParseError(f"Historical report month does not match {path.name}")
        incremental_partial = (
            document["schemaVersion"] == "1.1.0" and document["status"] == "partial"
        )
        if document["status"] not in {"generated", "verified"} and not incremental_partial:
            continue
        digest = hashlib.sha256(content).hexdigest()
        msrc_url = "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/" + msrc_document_id(path.stem)
        for row in document["updates"]:
            if incremental_partial and row["publicationStatus"] != "verified":
                continue
            if (
                row["kb"] == "NO PUBLICADO"
                or row["updateType"] != "security"
                or row["releaseDate"] is None
                or row["releaseDate"][:7] != path.stem
            ):
                continue
            sources = row.get("sources", [])
            msrc = next((s for s in sources if s["type"] == "msrc" and s["url"] == msrc_url), None)
            support = next(
                (
                    s
                    for s in sources
                    if s["type"] == "microsoft-support"
                    and _official_support_url(s["url"], row["kb"])
                ),
                None,
            )
            if msrc is None or support is None:
                continue
            os = row["os"]
            evidence.append(
                HistoricalUpdate(
                    kb=row["kb"],
                    os=OsIdentity(os["family"], os["version"], os["channel"], os["displayName"]),
                    release_date=date.fromisoformat(row["releaseDate"]),
                    report_path=path.relative_to(repository_root).as_posix(),
                    report_sha256=digest,
                    support_url=support["url"],
                    support_retrieved_at=datetime.fromisoformat(support["retrievedAt"]),
                    msrc_url=msrc["url"],
                    msrc_retrieved_at=datetime.fromisoformat(msrc["retrievedAt"]),
                )
            )
    return tuple(evidence)


def _official_support_url(url: str, kb: str) -> bool:
    parsed = urlsplit(url)
    number = re.escape(kb.removeprefix("KB"))
    return (
        parsed.scheme == "https"
        and parsed.netloc == "support.microsoft.com"
        and not parsed.query
        and not parsed.fragment
        and re.search(rf"(?:/help/{number}(?:/|$)|\bkb{number}\b)", parsed.path, re.IGNORECASE)
        is not None
    )
