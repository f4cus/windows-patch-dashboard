from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from windows_patch_collector.sources.microsoft_support import (
    _aggregate_known_issue_status,
    _classify_known_issue_item,
    parse_support_article,
)

FIXTURE = Path(__file__).parent / "fixtures" / "microsoft-support-known-issues.json"


def test_official_support_partial_resolution_regression() -> None:
    evidence = json.loads(FIXTURE.read_text("utf-8"))
    expected = {
        "KB5126835": "open",
        "KB5126836": "open",
        "KB5126868": "open",
        "KB5126651": "open",
        "KB5126655": "open",
        "KB5126646": "open",
        "KB5126653": "none",
        "KB5127648": "open",
        "KB5127646": "open",
    }
    actual = {}
    for kb, value in evidence["articles"].items():
        article = parse_support_article(
            value["html"].encode(),
            expected_kb=kb,
            source_url=value["source_url"],
            retrieved_at=datetime.fromisoformat(value["retrieved_at"]),
        )
        actual[kb] = article.known_issues_status
        if kb in {"KB5126835", "KB5126836", "KB5126868", "KB5126651", "KB5127648", "KB5127646"}:
            assert "partially resolved" in article.known_issues_summary
            assert (
                "Microsoft is working to address the other symptoms" in article.known_issues_summary
            )
    assert actual == expected


# These synthetic language cases exercise generic semantics, not Microsoft provenance.
@pytest.mark.parametrize(
    "text",
    [
        "This issue is partially resolved in an update.",
        "This issue was partly fixed by an update.",
        "This issue is resolved in an update, but symptoms remain.",
        "This issue was resolved in an update. Users still experience failures.",
        "This issue is resolved in an update. Microsoft is working on a resolution.",
        "This issue is not fully resolved in an update.",
        "This issue is not yet resolved in an update.",
        "This issue is mitigated by a workaround. Remaining symptoms require a fix.",
        "This issue is resolved in some cases. Not all symptoms are fixed.",
        "Este problema se ha resuelto parcialmente en una actualización.",
        "Este problema está parcialmente resuelto en una actualización.",
        "Este problema se ha resuelto en parte en una actualización.",
        "Este problema está resuelto, pero hay síntomas pendientes.",
        "Este problema se resolvió. Microsoft está trabajando en una solución.",
        "Este problema todavía no está resuelto.",
        "Hay una solución alternativa; los síntomas persisten.",
    ],
)
def test_partial_resolution_or_remaining_symptoms_are_open(text: str) -> None:
    assert _classify_known_issue_item(text) == "open"


@pytest.mark.parametrize(
    "text",
    [
        "This issue was resolved in an update.",
        "This issue is fully resolved by an update.",
        "The issue has been completely fixed by an update.",
        "This issue is fully resolved in an update. No remaining symptoms are reported.",
        "This issue is resolved in an update. The workaround is no longer necessary.",
        "This issue is resolved in an update, which does not require additional action.",
        "This issue is resolved in an update. Users may install the update normally.",
        "Resolved in an update.",
        "After installing an update, users might encounter errors. "
        "A workaround was available. This issue is resolved in a later update.",
        "Este problema se resolvió en una actualización.",
        "Este problema se ha resuelto completamente en una actualización.",
        "Este problema está resuelto en una actualización.",
        "Este problema se ha corregido completamente. No hay síntomas pendientes.",
        "Después de instalar una actualización, los usuarios no pueden iniciar sesión. "
        "Este problema se ha resuelto en una actualización posterior.",
    ],
)
def test_complete_resolution_including_historical_symptoms_is_resolved(text: str) -> None:
    assert _classify_known_issue_item(text) == "resolved"


@pytest.mark.parametrize(
    "text",
    [
        "This issue may be resolved in a future update.",
        "This issue will be resolved in a future update.",
        "This issue is expected to be resolved in an update.",
        "There is no confirmation that this issue is resolved in an update.",
        "Other issues were resolved in an update; the status of this issue is unclear.",
        "Este problema podría estar resuelto en una actualización.",
        "Este problema se resolverá en una actualización futura.",
        "Hay información sobre este problema, sin un estado verificable.",
        "No se ha confirmado que este problema está resuelto en una actualización.",
        "Microsoft is not currently aware of any issues. This issue is resolved in an update.",
        "Microsoft no tiene conocimiento de ningún problema. Este problema está resuelto.",
    ],
)
def test_insufficient_uncertain_or_contradictory_evidence_is_unknown(text: str) -> None:
    assert _classify_known_issue_item(text) == "unknown"


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        (["This issue is resolved in an update.", "Another issue is partially resolved."], "open"),
        (["Este problema está resuelto.", "Hay síntomas pendientes en otro problema."], "open"),
        (
            ["This issue is resolved in an update.", "An unclassified issue is documented."],
            "unknown",
        ),
        (
            ["Este problema se ha resuelto.", "Información insuficiente sobre otro problema."],
            "unknown",
        ),
        (
            ["This issue is resolved in an update.", "The issue has been fully resolved."],
            "resolved",
        ),
        (["Este problema se ha resuelto.", "Este problema está resuelto."], "resolved"),
        (["Microsoft is not currently aware of any issues with this update."], "none"),
        (["Microsoft no tiene conocimiento de ningún problema."], "none"),
    ],
)
def test_multiple_issues_preserve_conservative_aggregation(items: list[str], expected: str) -> None:
    assert _aggregate_known_issue_status(items) == expected


def test_remaining_issue_in_same_item_cannot_be_hidden_by_resolution() -> None:
    text = "This issue is resolved in an update. After installing it, another feature may fail."
    assert _classify_known_issue_item(text) == "open"
