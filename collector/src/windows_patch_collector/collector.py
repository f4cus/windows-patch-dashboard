"""Orchestrate official-source collection without coupling parsers to the schema."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import partial
from typing import Any

from windows_patch_collector.errors import (
    CollectionConflictError,
    CollectorError,
    UnsupportedHotpatchError,
)
from windows_patch_collector.history import historical_match
from windows_patch_collector.http_client import MicrosoftHttpClient
from windows_patch_collector.models import (
    HistoricalUpdate,
    StructuredResult,
    StructuredSource,
    SupportArticle,
)
from windows_patch_collector.normalization import NormalizedReport, normalize_report
from windows_patch_collector.sources.microsoft_release_health import (
    fetch_message_center,
    fetch_support_links,
)
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
    support_history_fetcher: StructuredFetcher | None = None,
    support_fetcher: SupportFetcher = fetch_support_article,
    historical_updates: tuple[HistoricalUpdate, ...] = (),
    previous_report: dict[str, Any] | None = None,
    now: Callable[[], datetime] | None = None,
) -> CollectionResult:
    """Collect a month, allowing per-KB Support failures to produce honest partial data."""

    structured = structured_fetcher(client, month)
    clock = now or (lambda: datetime.now(UTC))
    try:
        announcements = message_center_fetcher(client, month)
    except CollectorError as error:
        announcements = StructuredResult(
            (),
            structured.source_url,
            structured.retrieved_at,
            (f"OOB discovery unavailable: {error}",),
        )
    if support_history_fetcher is not None:
        exceptional = support_history_fetcher(client, month)
        announcements = StructuredResult(
            announcements.updates + exceptional.updates,
            announcements.source_url,
            announcements.retrieved_at,
            announcements.warnings + exceptional.warnings,
        )
    combined = list(structured.updates)
    for update in announcements.updates:
        matches = [
            (index, prior)
            for index, prior in enumerate(combined)
            if (prior.os, prior.kb) == (update.os, update.kb)
        ]
        if not matches:
            combined.append(update)
        for index, prior in matches:
            if prior.release_date_explicit and prior.release_date != update.release_date:
                raise CollectionConflictError(
                    f"Official date conflict for {update.kb}: "
                    f"MSRC={prior.release_date.isoformat()}, "
                    f"message center={update.release_date.isoformat()}"
                )
            subtype = (
                "Monthly Rollup"
                if "monthly rollup"
                in {prior.source_subtype.casefold(), update.source_subtype.casefold()}
                else update.source_subtype
            )
            combined[index] = replace(
                update,
                source_subtype=subtype,
                supersedes=prior.supersedes,
                additional_sources=prior.additional_sources
                + (StructuredSource(prior.source_type, prior.source_url, prior.retrieved_at),),
            )
    structured = StructuredResult(
        tuple(combined),
        structured.source_url,
        structured.retrieved_at,
        structured.warnings + announcements.warnings,
    )
    historical_by_key = {(item.os, item.kb): item for item in historical_updates}
    kbs = sorted(
        {
            update.kb
            for update in structured.updates
            if historical_match(update, month, historical_by_key) is None
        }
    )
    articles: dict[str, SupportArticle] = {}
    failures: dict[str, str] = {}
    checked_at: dict[str, datetime] = {}
    excluded_kbs: set[str] = set()
    support_links: dict[str, tuple[str, ...]] | None = None
    link_failure: CollectorError | None = None

    def linked_urls(kb: str) -> tuple[str, ...]:
        nonlocal support_links, link_failure
        known_urls = tuple(
            update.support_url
            for update in structured.updates
            if update.kb == kb and update.support_url is not None
        ) + tuple(update.support_url for update in historical_updates if update.kb == kb)
        if link_failure is not None:
            if known_urls:
                return tuple(dict.fromkeys(known_urls))
            raise link_failure
        if support_links is None:
            try:
                support_links = fetch_support_links(client)
            except CollectorError as error:
                link_failure = error
                if not known_urls:
                    raise
                return tuple(dict.fromkeys(known_urls))
        return tuple(dict.fromkeys(known_urls + support_links.get(kb, ())))

    for kb in kbs:
        try:
            if support_fetcher is fetch_support_article:
                with client.article_session() as article_client:
                    articles[kb] = fetch_support_article(
                        article_client, kb, fallback_urls=partial(linked_urls, kb)
                    )
            else:
                articles[kb] = support_fetcher(client, kb)
        except UnsupportedHotpatchError:
            excluded_kbs.add(kb)
        except CollectorError as error:
            failures[kb] = str(error)
        finally:
            checked_at[kb] = clock().astimezone(UTC)

    for update in announcements.updates:
        article = articles.get(update.kb)
        if article is not None and not article.is_out_of_band:
            raise CollectionConflictError(
                "Microsoft Support does not confirm announced OOB "
                f"{update.os.display_name} {update.kb}"
            )

    normalized = normalize_report(
        month=month,
        structured=structured,
        support_articles=articles,
        support_failures=failures,
        generated_at=clock().astimezone(UTC),
        excluded_kbs=frozenset(excluded_kbs),
        historical_updates=historical_updates,
        previous_report=previous_report,
        support_checked_at=checked_at,
    )
    return CollectionResult(normalized, len(articles), len(kbs), len(excluded_kbs))
