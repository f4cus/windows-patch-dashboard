from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from windows_patch_collector.errors import HttpFetchError
from windows_patch_collector.http_client import USER_AGENT, MicrosoftHttpClient


def test_retries_transient_response_then_succeeds() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["User-Agent"] == USER_AGENT
        return httpx.Response(503 if calls < 3 else 200, content=b"ok", request=request)

    with MicrosoftHttpClient(
        transport=httpx.MockTransport(handler),
        sleeper=sleeps.append,
        now=lambda: datetime(2026, 8, 13, tzinfo=UTC),
    ) as client:
        response = client.get("https://api.msrc.microsoft.com/test")

    assert response.content == b"ok"
    assert calls == 3
    assert sleeps == [0.5, 1.0]


def test_retry_exhaustion_raises_useful_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, request=request)

    with (
        MicrosoftHttpClient(
            transport=httpx.MockTransport(handler), attempts=2, sleeper=lambda _: None
        ) as client,
        pytest.raises(HttpFetchError, match="HTTP 503"),
    ):
        client.get("https://api.msrc.microsoft.com/test")
    assert calls == 2


def test_non_transient_http_failure_is_not_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404, request=request)

    with (
        MicrosoftHttpClient(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(HttpFetchError, match="HTTP 404"),
    ):
        client.get("https://support.microsoft.com/missing")
    assert calls == 1
