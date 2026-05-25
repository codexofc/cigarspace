# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Fetcher port — abstract HTTP fetch contract.

Lives in application/ports because use cases consume IFetcher to acquire
remote content. The concrete implementation (httpx, curl_cffi, …) is an
infrastructure detail.

The DTOs and exception hierarchy travel through this port; they are
deliberately framework-agnostic (no httpx types leak into application code).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


class FetchRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str = Field(min_length=1)
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    body: bytes | None = None
    timeout_s: float = Field(default=30.0, ge=0)
    proxy_url: str | None = None
    follow_redirects: bool = True


class FetchResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    url: str  # final URL after redirects
    status_code: int = Field(ge=100, le=599)
    headers: dict[str, str]
    body: bytes
    elapsed_s: float = Field(ge=0)
    fetched_at: datetime

    @property
    def text(self) -> str:
        # Charset detection follows httpx semantics: trust Content-Type, else utf-8 with
        # replacement for invalid bytes (we never want a decode error to crash a parser).
        encoding = "utf-8"
        ct = self.headers.get("content-type", "").lower()
        if "charset=" in ct:
            encoding = ct.split("charset=", 1)[1].split(";", 1)[0].strip() or "utf-8"
        return self.body.decode(encoding, errors="replace")


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class FetchError(Exception):
    """Base error raised by any IFetcher implementation."""

    def __init__(self, message: str, *, url: str | None = None) -> None:
        super().__init__(message)
        self.url = url


class FetchTimeoutError(FetchError):
    """The remote did not answer within timeout_s. Retriable."""


class NetworkError(FetchError):
    """DNS / TCP / TLS failure. Retriable."""


class RateLimitedError(FetchError):
    """HTTP 429. Retriable, honour Retry-After header if present."""

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        retry_after_s: float | None = None,
    ) -> None:
        super().__init__(message, url=url)
        self.retry_after_s = retry_after_s


class ForbiddenError(FetchError):
    """HTTP 403. Retriable with escalation to a different proxy tier."""


class ServerError(FetchError):
    """HTTP 5xx. Retriable."""

    def __init__(
        self, message: str, *, url: str | None = None, status_code: int | None = None
    ) -> None:
        super().__init__(message, url=url)
        self.status_code = status_code


class PermanentClientError(FetchError):
    """HTTP 4xx (other than 429/403). Not retriable."""

    def __init__(
        self, message: str, *, url: str | None = None, status_code: int | None = None
    ) -> None:
        super().__init__(message, url=url)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Port
# ---------------------------------------------------------------------------


class IFetcher(Protocol):
    """A single-shot HTTP fetch. Implementations MUST raise one of the
    FetchError subclasses on failure — never propagate framework exceptions."""

    async def fetch(self, request: FetchRequest) -> FetchResponse: ...
    async def aclose(self) -> None: ...
