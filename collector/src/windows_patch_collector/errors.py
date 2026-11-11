"""Collector-specific failures with concise, actionable messages."""


class CollectorError(RuntimeError):
    """Base class for expected collection failures."""


class SourceParseError(CollectorError):
    """Raised when an official source no longer matches its supported structure."""


class CollectionConflictError(CollectorError):
    """Raised when official sources disagree on a non-inferable fact."""


class HttpFetchError(CollectorError):
    """Raised after an HTTP request fails or exhausts its bounded retries."""

    def __init__(self, message: str, *, final_url: str | None = None) -> None:
        super().__init__(message)
        self.final_url = final_url


class UnsupportedHotpatchError(CollectorError):
    """Raised when an official Support redirect identifies a hotpatch-only package."""
