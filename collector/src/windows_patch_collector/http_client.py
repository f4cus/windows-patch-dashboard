"""Small, testable HTTP boundary for public Microsoft sources."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from windows_patch_collector.errors import HttpFetchError

USER_AGENT = "windows-patch-dashboard/0.1 (+https://github.com/windows-patch-dashboard)"
TRANSIENT_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class FetchedResponse:
    """Response bytes plus the actual official URL and retrieval instant."""

    content: bytes
    url: str
    retrieved_at: datetime


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
                    f"GET {url} returned HTTP {response.status_code} ({response.reason_phrase})"
                )
            return FetchedResponse(
                content=response.content,
                url=str(response.url),
                retrieved_at=self._now().astimezone(UTC),
            )

        detail = f": {last_error}" if last_error is not None else ""
        raise HttpFetchError(f"GET {url} failed after {self._attempts} attempts{detail}")
