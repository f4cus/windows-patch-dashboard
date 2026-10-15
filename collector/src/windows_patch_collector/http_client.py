"""Small, testable HTTP boundary for public Microsoft sources."""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import httpx

from windows_patch_collector.errors import HttpFetchError

USER_AGENT = "windows-patch-dashboard/0.1 (+https://github.com/windows-patch-dashboard)"
TRANSIENT_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})
_PUBLIC_DIAGNOSTIC_PATHS = {
    "support.microsoft.com": re.compile(
        r"/(?:[a-z]{2}-[a-z]{2}/)?(?:help/[0-9]{6,8}|topic|servicing/os)(?=/|$)",
        re.IGNORECASE,
    ),
    "api.msrc.microsoft.com": re.compile(
        r"/(?:cvrf/v3\.0/cvrf/[0-9]{4}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"|csaf/advisories/index\.txt)(?=/|$)",
        re.IGNORECASE,
    ),
    "learn.microsoft.com": re.compile(
        r"/(?:[a-z]{2}-[a-z]{2}/)?windows/release-health/(?:windows-message-center"
        r"|windows-server-release-info|windows11-release-information)(?=/|$)",
        re.IGNORECASE,
    ),
}


def diagnostic_url(url: str) -> str:
    """Keep known Microsoft routes; hide unknown paths, credentials and parameters."""

    parsed = urlsplit(url)
    path = parsed.path
    if path not in {"", "/"}:
        pattern = _PUBLIC_DIAGNOSTIC_PATHS.get(parsed.hostname or "")
        match = pattern.match(path) if pattern is not None else None
        if match is None:
            path = "/[redacted]"
        elif path[match.end() :] not in {"", "/"}:
            path = match.group() + "/[redacted]"
    return urlunsplit((parsed.scheme, parsed.netloc.rsplit("@", 1)[-1], path, "", ""))


@dataclass(frozen=True, slots=True)
class FetchedResponse:
    """Response bytes plus the actual official URL and retrieval instant."""

    content: bytes
    url: str
    retrieved_at: datetime
    status_code: int


class MicrosoftHttpClient:
    """HTTP client with explicit timeouts and bounded transient retries."""

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        attempts: int = 3,
        backoff_seconds: float = 0.5,
        sleeper: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least one")
        self._attempts = attempts
        self._backoff_seconds = backoff_seconds
        self._sleeper = sleeper
        self._now = now or (lambda: datetime.now(UTC))
        self._client = httpx.Client(
            transport=transport,
            follow_redirects=True,
            timeout=httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=10.0),
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        )

    def __enter__(self) -> MicrosoftHttpClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get(self, url: str) -> FetchedResponse:
        """Fetch a URL or raise a stable error after transient retries."""

        last_error: Exception | None = None
        for attempt in range(1, self._attempts + 1):
            try:
                response = self._client.get(url)
            except httpx.TransportError as error:
                last_error = error
                if attempt < self._attempts:
                    self._sleeper(self._backoff_seconds * attempt)
                    continue
                break

            if response.status_code in TRANSIENT_STATUS_CODES and attempt < self._attempts:
                self._sleeper(self._backoff_seconds * attempt)
                continue
            if response.is_error:
                raise HttpFetchError(
                    f"GET {diagnostic_url(url)} returned HTTP {response.status_code} "
                    f"({response.reason_phrase}); http_status={response.status_code} "
                    f"final_url={diagnostic_url(str(response.url))!r}"
                )
            return FetchedResponse(
                content=response.content,
                url=str(response.url),
                retrieved_at=self._now().astimezone(UTC),
                status_code=response.status_code,
            )

        detail = ""
        if last_error is not None:
            detail = f"; error_type={type(last_error).__name__}"
            cause = last_error.__cause__ or last_error.__context__
            cause_types: list[str] = []
            for _ in range(5):
                if cause is None:
                    break
                cause_types.append(type(cause).__name__)
                cause = cause.__cause__ or cause.__context__
            if cause_types:
                detail += f"; cause_types={'->'.join(cause_types)}"
        raise HttpFetchError(
            f"GET {diagnostic_url(url)} failed after {self._attempts} attempts{detail}"
        ) from last_error
