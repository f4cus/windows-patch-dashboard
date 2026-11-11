"""Bounded discovery of dated exceptional OOB links in official product histories."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from windows_patch_collector.errors import CollectionConflictError, CollectorError, SourceParseError
from windows_patch_collector.http_client import MicrosoftHttpClient
from windows_patch_collector.lifecycle import ended_product_history_pages
from windows_patch_collector.models import StructuredResult, StructuredUpdate
from windows_patch_collector.sources.microsoft_support import (
    _OOB_TITLE_PATTERN,
    _assert_support_url,
    _package_kind,
    _parse_article_date,
    parse_support_article,
)


def fetch_post_esu_oob(client: MicrosoftHttpClient, month: str) -> StructuredResult:
    """Follow explicit, dated OOB navigation labels; target articles still need verification."""
    updates: dict[tuple[str, str], StructuredUpdate] = {}
    warnings: list[str] = []
    retrieved = datetime.now(UTC)
    source_url = "https://support.microsoft.com/"
    for identity, url in ended_product_history_pages(month):
        try:
            with client.article_session() as session:
                response = session.get(url)
            _assert_support_url(response.url)
            kb_match = re.search(r"\bkb[0-9]+\b", url, re.IGNORECASE)
            if kb_match is None:
                raise SourceParseError("Product history source lacks a verified KB identifier")
            article = parse_support_article(
                response.content,
                expected_kb=kb_match.group().upper(),
                source_url=response.url,
                retrieved_at=response.retrieved_at,
            )
            if article.applies_to is None or identity not in article.applies_to:
                raise SourceParseError("Product history applicability could not be verified")
            soup = BeautifulSoup(response.content, "lxml")
            navigation = soup.select_one("#learnRenderLeftNav .learnRenderLeftNavActiveCategory")
            if navigation is None:
                navigation = soup.select_one("#learnRenderLeftNav")
            if navigation is None:
                raise SourceParseError("Product history navigation unavailable")
            for link in navigation.select("a.learnRenderLeftNavLink[href]"):
                label = " ".join(link.get_text(" ", strip=True).split())
                kb = re.search(r"\bKB[0-9]{6,8}\b", label, re.IGNORECASE)
                if kb is None or _OOB_TITLE_PATTERN.search(label) is None:
                    continue
                release = _parse_article_date(label)
                if release.strftime("%Y-%m") != month:
                    continue
                linked = urljoin(response.url, str(link["href"]))
                _assert_support_url(linked)
                candidate = StructuredUpdate(
                    kb.group().upper(),
                    identity,
                    release,
                    "oob",
                    response.url,
                    response.retrieved_at,
                    "Monthly Rollup"
                    if _package_kind(label) == "monthly-rollup"
                    else "Out-of-band Support history",
                    support_url=linked,
                    source_type="microsoft-support",
                )
                key = (identity.display_name, candidate.kb)
                prior = updates.get(key)
                if prior is not None and prior.release_date != candidate.release_date:
                    raise CollectionConflictError(
                        f"Conflicting official OOB history dates for {candidate.kb}"
                    )
                updates[key] = candidate
            source_url, retrieved = response.url, response.retrieved_at
        except CollectionConflictError:
            raise
        except CollectorError as error:
            warnings.append(
                f"{identity.display_name}: exceptional OOB discovery unavailable: {error}"
            )
    return StructuredResult(tuple(updates.values()), source_url, retrieved, tuple(warnings))
