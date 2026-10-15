from __future__ import annotations

import socket
import ssl
from datetime import UTC, datetime

import httpx
import pytest

from windows_patch_collector.errors import HttpFetchError
from windows_patch_collector.http_client import USER_AGENT, MicrosoftHttpClient, diagnostic_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://user:password@support.microsoft.com/es-es/help/5126835?token=secret#private",
            "https://support.microsoft.com/es-es/help/5126835",
        ),
        (
            "https://support.microsoft.com/en-us/help/5126835/path-secret",
            "https://support.microsoft.com/en-us/help/5126835/[redacted]",
        ),
        (
            "https://support.microsoft.com/en-us/topic/path-secret",
            "https://support.microsoft.com/en-us/topic/[redacted]",
        ),
        (
            "https://support.microsoft.com/en-us/servicing/os/server-2012/2026/10/path-secret",
            "https://support.microsoft.com/en-us/servicing/os/[redacted]",
        ),
        (
            "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Oct?token=secret",
            "https://api.msrc.microsoft.com/cvrf/v3.0/cvrf/2026-Oct",
        ),
        (
            "https://api.msrc.microsoft.com/csaf/advisories/index.txt",
            "https://api.msrc.microsoft.com/csaf/advisories/index.txt",
        ),
        (
            "https://learn.microsoft.com/en-us/windows/release-health/windows-message-center",
            "https://learn.microsoft.com/en-us/windows/release-health/windows-message-center",
        ),
        (
            "https://learn.microsoft.com/en-us/windows/release-health/"
            "windows-server-release-info/path-secret",
            "https://learn.microsoft.com/en-us/windows/release-health/"
            "windows-server-release-info/[redacted]",
        ),
        (
            "https://support.microsoft.com/en-us/session/path-secret",
            "https://support.microsoft.com/[redacted]",
        ),
        (
            "https://support.microsoft.com/en-us/%74opic/path-secret",
            "https://support.microsoft.com/[redacted]",
        ),
        (
            "https://support.microsoft.com/en-us/help/5126835123456",
            "https://support.microsoft.com/[redacted]",
        ),
        (
            "https://login.microsoftonline.com/tenant-secret/oauth2/path-secret",
            "https://login.microsoftonline.com/[redacted]",
        ),
        (
            "https://support.microsoft.com.example.com/en-us/help/5126835/path-secret",
            "https://support.microsoft.com.example.com/[redacted]",
        ),
    ],
)
def test_diagnostic_url_preserves_only_known_public_routing(url: str, expected: str) -> None:
    assert diagnostic_url(url) == expected


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


def test_redirected_http_failure_reports_final_url_without_sensitive_data() -> None:
    requested = "https://user:password@support.microsoft.com/help/5000000?token=secret#private"
    final = "https://support.microsoft.com/en-us/session/path-secret?token=redirect-secret#private"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/help/"):
            return httpx.Response(302, headers={"Location": final}, request=request)
        return httpx.Response(
            403,
            request=request,
            headers={"Set-Cookie": "sensitive-cookie"},
            content=b"<html>sensitive-body</html>",
        )

    with (
        MicrosoftHttpClient(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(HttpFetchError) as raised,
    ):
        client.get(requested)

    message = str(raised.value)
    assert "GET https://support.microsoft.com/help/5000000 returned HTTP 403 (Forbidden)" in message
    assert "http_status=403" in message
    assert "final_url='https://support.microsoft.com/[redacted]'" in message
    assert all(
        sensitive not in message
        for sensitive in ("user", "password", "secret", "private", "cookie", "body", "<html>")
    )


def test_transport_failure_preserves_cause_and_reports_error_type() -> None:
    calls = 0
    original = httpx.ReadTimeout("sensitive transport detail")

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise original

    with (
        MicrosoftHttpClient(
            transport=httpx.MockTransport(handler), attempts=2, sleeper=lambda _: None
        ) as client,
        pytest.raises(HttpFetchError) as raised,
    ):
        client.get("https://support.microsoft.com/test?token=secret")

    assert calls == 2
    assert "failed after 2 attempts; error_type=ReadTimeout" in str(raised.value)
    assert raised.value.__cause__ is original
    assert "secret" not in str(raised.value)
    assert "sensitive transport detail" not in str(raised.value)


@pytest.mark.parametrize("link", ["__cause__", "__context__"])
@pytest.mark.parametrize(
    "underlying",
    [
        socket.gaierror(socket.EAI_NONAME, "sensitive DNS host or token"),
        ssl.SSLCertVerificationError(1, "sensitive TLS certificate or token"),
    ],
)
def test_transport_failure_reports_underlying_types_without_messages(
    underlying: Exception, link: str
) -> None:
    calls = 0
    sleeps: list[float] = []
    wrapper = OSError("sensitive wrapper detail")
    setattr(wrapper, link, underlying)
    original = httpx.ConnectError("sensitive transport detail")
    setattr(original, link, wrapper)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise original

    with (
        MicrosoftHttpClient(
            transport=httpx.MockTransport(handler), attempts=2, sleeper=sleeps.append
        ) as client,
        pytest.raises(HttpFetchError) as raised,
    ):
        client.get("https://support.microsoft.com/en-us/help/5126835")

    message = str(raised.value)
    assert "error_type=ConnectError" in message
    assert f"cause_types=OSError->{type(underlying).__name__}" in message
    assert "sensitive" not in message
    assert "token" not in message
    assert raised.value.__cause__ is original
    assert calls == 2
    assert sleeps == [0.5]
