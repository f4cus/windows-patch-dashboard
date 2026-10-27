"""One-time live integration check; removed before merging the fix."""

from windows_patch_collector.collector import collect_month
from windows_patch_collector.http_client import MicrosoftHttpClient


def test_live_october_msrc_support_collection() -> None:
    with MicrosoftHttpClient() as client:
        report = collect_month("2026-10", client=client).normalized.document

    assert report["reportMonth"] == "2026-10"
    rollups = [
        item
        for item in report["updates"]
        if item["os"]["version"] == "2012 R2" and item["updateType"] == "security"
    ]
    assert len(rollups) == 1
    assert rollups[0]["kb"] == "KB5126836"
