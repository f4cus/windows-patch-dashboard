"""Orchestrate official-source collection without coupling parsers to the schema."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from windows_patch_collector.errors import CollectorError, UnsupportedHotpatchError
from windows_patch_collector.http_client import MicrosoftHttpClient
from windows_patch_collector.models import StructuredResult, SupportArticle
from windows_patch_collector.normalization import NormalizedReport, normalize_report
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
    support_fetcher: SupportFetcher = fetch_support_article,
    now: Callable[[], datetime] | None = None,
) -> CollectionResult:
    """Collect a month, allowing per-KB Support failures to produce honest partial data."""

    structured = structured_fetcher(client, month)
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
