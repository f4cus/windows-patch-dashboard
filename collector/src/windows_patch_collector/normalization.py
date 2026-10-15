"""Normalize parsed Microsoft evidence into the existing monthly report contract."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from windows_patch_collector.calendar import patch_tuesday
from windows_patch_collector.errors import CollectionConflictError
from windows_patch_collector.http_client import diagnostic_url
from windows_patch_collector.models import (
    OsIdentity,
    StructuredResult,
    StructuredUpdate,
    SupportArticle,
)
from windows_patch_collector.ordering import sort_updates
from windows_patch_collector.products import (
    EXPECTED_SERVER_IDENTITIES,
    WINDOWS_SERVER_2012,
    WINDOWS_SERVER_2012_R2,
)

_UNAVAILABLE_CHANGES = (
    "No disponible: no se pudo verificar el contenido del artículo de Microsoft Support."
)
_UNAVAILABLE_RESOLVED = (
    "No disponible: no se pudieron verificar correcciones documentadas por Microsoft Support."
)
_UNAVAILABLE_KNOWN = (
    "No disponible: no se pudo verificar el estado de problemas conocidos en Microsoft Support."
)
_NOT_PUBLISHED_CHANGES = (
    "No publicado: MSRC no identifica un Monthly Rollup ESU verificable para este producto y mes."
)
_NOT_PUBLISHED_RESOLVED = (
    "No disponible: no existe un artículo de actualización publicado que permita "
    "verificar correcciones."
)
_NOT_PUBLISHED_KNOWN = (
    "No disponible: no existe una publicación que permita verificar problemas conocidos."
)


@dataclass(frozen=True, slots=True)
class NormalizedReport:
    """Report document plus warnings retained by the CLI."""

    document: dict[str, Any]
    warnings: tuple[str, ...]


def iso_datetime(value: datetime) -> str:
    """Serialize an aware datetime as canonical UTC ISO-8601."""

    if value.tzinfo is None:
        raise ValueError("retrieval and generation times must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _source(source_type: str, url: str, retrieved_at: datetime) -> dict[str, str]:
    return {"type": source_type, "url": url, "retrievedAt": iso_datetime(retrieved_at)}


def _supports_identity(article: SupportArticle, identity: OsIdentity) -> bool:
    if article.applies_to is None:
        return False
    if identity.family == "Windows Server":
        return identity in article.applies_to
    versions = {product.version for product in article.applies_to if product.family == "Windows 11"}
    return set(identity.version.split("/")) <= versions


def _support_diagnostics(
    update: StructuredUpdate,
    article: SupportArticle | None,
    support_failures: Mapping[str, str],
) -> str:
    details = (
        f"kb={update.kb} os={update.os.display_name!r} msrc_subtype={update.source_subtype!r} "
    )
    if article is not None:
        return (
            details + f"support_verification=parsed package_kind={article.package_kind} "
            f"final_url={diagnostic_url(article.source_url)!r}"
        )
    state = "failed" if update.kb in support_failures else "unavailable"
    reason = support_failures.get(update.kb, "article unavailable")
    return details + f"support_verification={state} support_error={reason!r}"


def _select_updates(
    structured: StructuredResult,
    month: str,
    excluded_kbs: frozenset[str],
    support_articles: Mapping[str, SupportArticle],
    support_failures: Mapping[str, str],
) -> tuple[list[StructuredUpdate], list[str]]:
    expected_release = patch_tuesday(month)
    unique: dict[tuple[OsIdentity, str], StructuredUpdate] = {}
    monthly_by_os: dict[OsIdentity, list[StructuredUpdate]] = defaultdict(list)
    warnings = list(structured.warnings)

    for update in structured.updates:
        if update.kb in excluded_kbs:
            warnings.append(
                f"{update.kb}: ignored because Microsoft Support identifies it as hotpatch"
            )
            continue
        article = support_articles.get(update.kb)
        if article is not None:
            if update.release_date_explicit and article.release_date != update.release_date:
                raise CollectionConflictError(
                    f"Official date conflict for {update.kb}: "
                    f"MSRC={update.release_date.isoformat()}, "
                    f"Support={article.release_date.isoformat()}; "
                    + _support_diagnostics(update, article, support_failures)
                )
            if article.applies_to is not None and not _supports_identity(article, update.os):
                raise CollectionConflictError(
                    f"Official product conflict for {update.kb}: "
                    f"Support does not apply to {update.os.display_name}; "
                    + _support_diagnostics(update, article, support_failures)
                )
            if article.applies_to is None:
                warnings.append(f"{update.kb}: Microsoft Support product applicability unavailable")
            if not update.release_date_explicit:
                if article.release_date.strftime("%Y-%m") < month:
                    if not _supports_identity(article, update.os):
                        raise CollectionConflictError(
                            f"Cannot resolve historical candidate {update.kb} for "
                            f"{update.os.display_name} without Support product applicability; "
                            + _support_diagnostics(update, article, support_failures)
                        )
                    warnings.append(
                        f"{update.kb}: ignored historical CVRF candidate for "
                        f"{update.os.display_name}; "
                        f"Support release={article.release_date.isoformat()}"
                    )
                    continue
                update = replace(update, release_date=article.release_date)
            if article.package_kind in {"ssu", "security-only", "auxiliary"}:
                warnings.append(
                    f"{update.kb}: ignored {article.package_kind} package identified by Support"
                )
                continue
            if article.is_out_of_band and update.update_type == "security":
                update = replace(update, update_type="oob")
            if update.update_type == "security" and article.release_date != expected_release:
                raise CollectionConflictError(
                    f"Support date {article.release_date.isoformat()} for {update.kb} "
                    f"does not match Patch Tuesday {expected_release.isoformat()} "
                    "and Support does not identify an OOB; "
                    + _support_diagnostics(update, article, support_failures)
                )
        if update.update_type == "security" and update.release_date != expected_release:
            continue
        if update.os in {WINDOWS_SERVER_2012, WINDOWS_SERVER_2012_R2}:
            if article is not None and article.package_kind == "monthly-rollup":
                if not _supports_identity(article, update.os):
                    raise CollectionConflictError(
                        f"Cannot verify ESU Monthly Rollup {update.kb} product applicability; "
                        + _support_diagnostics(update, article, support_failures)
                    )
            elif update.source_subtype.casefold() != "monthly rollup":
                raise CollectionConflictError(
                    f"Cannot classify ESU candidate {update.kb} as a Monthly Rollup; "
                    "Microsoft Support verification required; "
                    + _support_diagnostics(update, article, support_failures)
                )
            elif article is not None and article.package_kind == "cumulative":
                raise CollectionConflictError(
                    f"Official package kind conflict for {update.kb}; "
                    + _support_diagnostics(update, article, support_failures)
                )
        key = (update.os, update.kb)
        existing = unique.get(key)
        if existing is not None and existing != update:
            raise CollectionConflictError(
                "Structured source returned conflicting records for "
                f"{update.os.display_name} {update.kb}"
            )
        unique[key] = update
        if update.update_type == "security":
            monthly_by_os[update.os].append(update)

    for identity, updates in monthly_by_os.items():
        distinct_kbs = {update.kb for update in updates}
        if len(distinct_kbs) > 1:
            verified_kbs = {
                kb
                for kb in distinct_kbs
                if kb in support_articles
                and kb not in support_failures
                and _supports_identity(support_articles[kb], identity)
                and support_articles[kb].release_date == expected_release
                and support_articles[kb].package_kind in {"cumulative", "monthly-rollup"}
            }
            if len(verified_kbs) == 1:
                selected_kb = next(iter(verified_kbs))
                unverified_kbs = sorted(distinct_kbs - verified_kbs)
                for kb in unverified_kbs:
                    unique.pop((identity, kb), None)
                warnings.append(
                    f"{identity.display_name}: selected Support-verified {selected_kb}; "
                    "CVRF also listed unverified monthly candidates: " + ", ".join(unverified_kbs)
                )
                continue
            raise CollectionConflictError(
                f"Multiple normal monthly KBs found for {identity.display_name}: "
                + ", ".join(sorted(distinct_kbs))
            )
    return list(unique.values()), warnings


def normalize_report(
    *,
    month: str,
    structured: StructuredResult,
    support_articles: Mapping[str, SupportArticle],
    support_failures: Mapping[str, str],
    generated_at: datetime,
    excluded_kbs: frozenset[str] = frozenset(),
) -> NormalizedReport:
    """Build a schema-shaped report from source-specific parsed evidence."""

    selected, warnings = _select_updates(
        structured, month, excluded_kbs, support_articles, support_failures
    )
    incomplete = bool(structured.warnings or support_failures)
    incomplete |= any(
        support_articles[update.kb].applies_to is None
        or support_articles[update.kb].package_kind == "unknown"
        for update in selected
        if update.kb in support_articles
    )
    present_monthly = {update.os for update in selected if update.update_type == "security"}

    for identity in EXPECTED_SERVER_IDENTITIES:
        if identity in present_monthly:
            continue
        if identity in {WINDOWS_SERVER_2012, WINDOWS_SERVER_2012_R2}:
            incomplete = True
            warnings.append(
                f"{identity.display_name}: no verified ESU Monthly Rollup; emitted NO PUBLICADO"
            )
        else:
            incomplete = True
            warnings.append(
                f"{identity.display_name}: no normal monthly security update discovered"
            )

    # Link an OOB only from an explicit structured supersedes relationship.
    superseding: dict[tuple[OsIdentity, str], str] = {}
    for update in selected:
        if update.update_type != "oob" or update.supersedes is None:
            continue
        key = (update.os, update.supersedes)
        existing = superseding.get(key)
        if existing is not None and existing != update.kb:
            raise CollectionConflictError(
                "Multiple OOB updates claim to supersede "
                f"{update.os.display_name} {update.supersedes}"
            )
        superseding[key] = update.kb

    output: list[dict[str, Any]] = []
    for update in selected:
        article = support_articles.get(update.kb)
        if article is not None and article.release_date != update.release_date:
            raise CollectionConflictError(
                f"Official date conflict for {update.kb}: MSRC={update.release_date.isoformat()}, "
                f"Support={article.release_date.isoformat()}"
            )
        sources = [_source(update.source_type, update.source_url, update.retrieved_at)]
        if article is None:
            changes = _UNAVAILABLE_CHANGES
            resolved = _UNAVAILABLE_RESOLVED
            known = _UNAVAILABLE_KNOWN
            known_status = "unknown"
            warnings.append(
                f"{update.kb}: Microsoft Support unavailable; "
                + _support_diagnostics(update, article, support_failures)
            )
        else:
            sources.append(_source("microsoft-support", article.source_url, article.retrieved_at))
            changes = article.changes_summary
            resolved = article.resolved_issues_summary
            known = article.known_issues_summary
            known_status = article.known_issues_status
            if known_status == "unknown":
                incomplete = True

        output.append(
            {
                "kb": update.kb,
                "os": update.os.as_report_value(),
                "updateType": update.update_type,
                "releaseDate": update.release_date.isoformat(),
                "changesSummary": changes,
                "resolvedIssuesSummary": resolved,
                "knownIssuesSummary": known,
                "knownIssuesStatus": known_status,
                "supersededBy": superseding.get((update.os, update.kb)),
                "sources": sources,
            }
        )

    for identity in (WINDOWS_SERVER_2012, WINDOWS_SERVER_2012_R2):
        if identity in present_monthly:
            continue
        output.append(
            {
                "kb": "NO PUBLICADO",
                "os": identity.as_report_value(),
                "updateType": "security",
                "releaseDate": None,
                "changesSummary": _NOT_PUBLISHED_CHANGES,
                "resolvedIssuesSummary": _NOT_PUBLISHED_RESOLVED,
                "knownIssuesSummary": _NOT_PUBLISHED_KNOWN,
                "knownIssuesStatus": "not-published",
                "supersededBy": None,
                "sources": [_source("msrc", structured.source_url, structured.retrieved_at)],
            }
        )

    document: dict[str, Any] = {
        "schemaVersion": "1.0.0",
        "reportMonth": month,
        "patchTuesdayDate": patch_tuesday(month).isoformat(),
        "generatedAt": iso_datetime(generated_at),
        "status": "partial" if incomplete else "generated",
        "updates": sort_updates(output),
    }
    return NormalizedReport(document, tuple(dict.fromkeys(warnings)))
