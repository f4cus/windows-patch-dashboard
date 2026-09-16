"""Orchestrate official-source collection without coupling parsers to the schema."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from windows_patch_collector.errors import (
    CollectionConflictError,
    CollectorError,
    UnsupportedHotpatchError,
)
from windows_patch_collector.http_client import MicrosoftHttpClient
from windows_patch_collector.models import StructuredResult, SupportArticle
from windows_patch_collector.normalization import NormalizedReport, normalize_report
from windows_patch_collector.sources.microsoft_release_health import fetch_message_center
from windows_patch_collector.sources.microsoft_support import fetch_support_article
from windows_patch_collector.sources.msrc_cvrf import fetch_cvrf

StructuredFetcher = Callable[[MicrosoftHttpClient, str], StructuredResult]
SupportFetcher = Callable[[MicrosoftHttpClient, str], SupportArticle]


@dataclass(frozen=True, slots=True)
class CollectionResult:
    """Normalized report plus concise execution counters."""

    normalized: NormalizedReport
    support_verified: int
    support_attempted: int
    hotpatch_excluded: int


def collect_month(
    month: str,
    *,
    client: MicrosoftHttpClient,
    structured_fetcher: StructuredFetcher = fetch_cvrf,
    message_center_fetcher: StructuredFetcher = fetch_message_center,
    support_fetcher: SupportFetcher = fetch_support_article,
    now: Callable[[], datetime] | None = None,
) -> CollectionResult:
    """Collect a month, allowing per-KB Support failures to produce honest partial data."""

    structured = structured_fetcher(client, month)
    announcements = message_center_fetcher(client, month)
    existing = {(update.os, update.kb): update for update in structured.updates}
    added = []
    for update in announcements.updates:
        prior = existing.get((update.os, update.kb))
        if prior is not None:
            if prior.release_date_explicit and prior.release_date != update.release_date:
                raise CollectionConflictError(
                    f"Official date conflict for {update.kb}: "
                    f"MSRC={prior.release_date.isoformat()}, "
                    f"message center={update.release_date.isoformat()}"
                )
            continue
        added.append(update)
    structured = StructuredResult(
        structured.updates + tuple(added),
        structured.source_url,
        structured.retrieved_at,
        structured.warnings + announcements.warnings,
    )
    kbs = sorted({update.kb for update in structured.updates})
    articles: dict[str, SupportArticle] = {}
    failures: dict[str, str] = {}
    excluded_kbs: set[str] = set()
    for kb in kbs:
        try:
            articles[kb] = support_fetcher(client, kb)
        except UnsupportedHotpatchError:
            excluded_kbs.add(kb)
        except CollectorError as error:
            failures[kb] = str(error)

    for update in announcements.updates:
        article = articles.get(update.kb)
        if article is not None and not article.is_out_of_band:
            raise CollectionConflictError(
                "Microsoft Support does not confirm announced OOB "
                f"{update.os.display_name} {update.kb}"
            )

    clock = now or (lambda: datetime.now(UTC))
    normalized = normalize_report(
        month=month,
        structured=structured,
        support_articles=articles,
        support_failures=failures,
        generated_at=clock().astimezone(UTC),
        excluded_kbs=frozenset(excluded_kbs),
    )
    return CollectionResult(normalized, len(articles), len(kbs), len(excluded_kbs))
