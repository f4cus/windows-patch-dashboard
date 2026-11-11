"""Preserve confirmed fields across incomplete refreshes without fabricating evidence."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from windows_patch_collector.errors import CollectionConflictError
from windows_patch_collector.ordering import sort_updates

CONTENT_FIELDS = ("changesSummary", "resolvedIssuesSummary", "knownIssuesSummary")


def available(text: str) -> bool:
    return bool(text.strip()) and not text.strip().startswith(
        ("No disponible", "Pendiente de verificación")
    )


def content_complete(row: dict[str, Any]) -> bool:
    return row["knownIssuesStatus"] != "unknown" and all(
        available(row[field]) for field in CONTENT_FIELDS
    )


def preserve_confirmed_fields(
    document: dict[str, Any],
    previous: dict[str, Any] | None,
    *,
    excluded_kbs: frozenset[str] = frozenset(),
) -> None:
    """Reuse only same-month KB/product facts with original official evidence."""
    if previous is None or previous["reportMonth"] != document["reportMonth"]:
        return
    prior = {}
    for row in previous["updates"]:
        sources = row["sources"] + row.get("retainedSources", [])
        types = {s["type"] for s in sources}
        if (
            row["kb"] != "NO PUBLICADO"
            and row["kb"] not in excluded_kbs
            and row.get("publicationStatus") != "pending"
            and "microsoft-support" in types
            and (
                types & {"msrc", "release-health"}
                or row["updateType"] == "oob"
                and row.get("publicationStatus") in {"verified", "partial"}
            )
        ):
            prior[(row["os"]["displayName"], row["kb"])] = row
    for row in document["updates"]:
        old = prior.get((row["os"]["displayName"], row["kb"]))
        if old is None:
            continue
        if row["releaseDate"] is not None and row["releaseDate"] != old["releaseDate"]:
            raise CollectionConflictError(
                f"Refresh date contradicts verified baseline for {row['kb']}"
            )
        retained = False
        if row["publicationStatus"] == "pending":
            row["releaseDate"] = old["releaseDate"]
            metadata_confirmed = old["updateType"] != "unknown" and (
                old.get("publicationStatus") in {"verified", "partial"}
                or previous["status"] in {"generated", "verified"}
            )
            if metadata_confirmed:
                row["updateType"] = old["updateType"]
                row["publicationStatus"] = "partial"
            if metadata_confirmed and old["supersededBy"] is not None:
                target = (row["os"]["displayName"], old["supersededBy"])
                if target in prior:
                    row["supersededBy"] = old["supersededBy"]
            retained = True
        for field in CONTENT_FIELDS:
            if not available(row[field]) and available(old[field]):
                row[field] = old[field]
                if field == "knownIssuesSummary":
                    row["knownIssuesStatus"] = old["knownIssuesStatus"]
                retained = True
        if retained:
            sources = old.get("retainedSources", []) + old["sources"]
            retained_sources: dict[tuple[str, str, str | None], Any] = {}
            for source in sources:
                if source["type"] != "microsoft-support":
                    continue
                source_key = (source["type"], source["url"], source.get("retrievedAt"))
                retained_sources.setdefault(source_key, deepcopy(source))
            row["retainedSources"] = list(retained_sources.values())
            if row["publicationStatus"] != "pending":
                row["publicationStatus"] = "partial"
    present = {(row["os"]["displayName"], row["kb"]) for row in document["updates"]}
    for key, old in prior.items():
        if key in present or old["updateType"] != "oob":
            continue
        row = deepcopy(old)
        row["publicationStatus"] = "partial"
        sources = old["sources"] + old.get("retainedSources", [])
        source = next(s for s in sources if s["type"] == "microsoft-support")
        row["verification"] = {
            "status": "unavailable",
            "url": source["url"],
            "checkedAt": document["generatedAt"],
            "detail": "OOB not rediscovered; retained verified same-month evidence",
        }
        document["updates"] = [
            r
            for r in document["updates"]
            if not (r["kb"] == "NO PUBLICADO" and r.get("lifecycle") and r["os"] == row["os"])
        ]
        document["updates"].append(row)
        document["status"] = "partial"
    document["updates"] = sort_updates(document["updates"])
