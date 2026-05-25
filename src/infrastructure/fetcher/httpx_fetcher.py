# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""HttpxFetcher — IFetcher implementation backed by httpx.AsyncClient (L0 tier).

This is the default, no-frills fetcher: native TCP/TLS, no proxy, no
fingerprint impersonation. Used for sites without aggressive WAF.

The class owns a single AsyncClient reused across requests for keepalive
benefits; remember to call `await fetcher.aclose()` on shutdown.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import httpx

from application.ports.fetcher import (
    FetchError,
    FetchRequest,
    FetchResponse,
    FetchTimeoutError,
    ForbiddenError,
    NetworkError,
    PermanentClientError,
    RateLimitedError,
    ServerError,
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def _parse_retry_after(value: str | None) -> float | None:
    """Best-effort parsing of the Retry-After header (seconds form)."""

    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        # HTTP-date form intentionally ignored for now — uncommon in scraping.
        return None


class HttpxFetcher:
    """IFetcher implementation using httpx.AsyncClient."""

    def __init__(
        self,
        *,
        default_headers: dict[str, str] | None = None,
        max_connections: int = 100,
        max_keepalive: int = 20,
        verify_tls: bool = True,
        proxy_url: str | None = None,
    ) -> None:
        self._default_headers = dict(DEFAULT_HEADERS)
        if default_headers:
            self._default_headers.update(default_headers)

        limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive,
        )
        self._client = httpx.AsyncClient(
            limits=limits,
            verify=verify_tls,
            http2=False,  # http2 needs the h2 extra; defer until needed
            proxy=proxy_url,
        )

    async def fetch(self, request: FetchRequest) -> FetchResponse:
        headers = {**self._default_headers, **request.headers}

        if request.proxy_url is not None:
            raise NotImplementedError(
                "Per-request proxy override is not supported on HttpxFetcher; "
                "construct a dedicated HttpxFetcher(proxy_url=...) instance for "
                "proxied traffic (used by the L1/L2 tiers in )."
            )

        started = time.monotonic()
        try:
            response = await self._client.request(
                request.method,
                request.url,
                headers=headers,
                content=request.body,
                timeout=request.timeout_s,
                follow_redirects=request.follow_redirects,
            )
        except httpx.TimeoutException as exc:
            raise FetchTimeoutError(str(exc), url=request.url) from exc
        except httpx.NetworkError as exc:
            raise NetworkError(str(exc), url=request.url) from exc
        except httpx.HTTPError as exc:
            # Anything else (proxy, protocol, ...) -> treat as a network error.
            raise NetworkError(str(exc), url=request.url) from exc

        elapsed = time.monotonic() - started
        status = response.status_code
        body = response.content
        headers_out = {k.lower(): v for k, v in response.headers.items()}
        url_out = str(response.url)

        if 200 <= status < 400:
            return FetchResponse(
                url=url_out,
                status_code=status,
                headers=headers_out,
                body=body,
                elapsed_s=elapsed,
                fetched_at=datetime.now(tz=UTC),
            )

        if status == 429:
            raise RateLimitedError(
                f"HTTP 429 from {url_out}",
                url=url_out,
                retry_after_s=_parse_retry_after(headers_out.get("retry-after")),
            )
        if status == 403:
            raise ForbiddenError(f"HTTP 403 from {url_out}", url=url_out)
        if 500 <= status < 600:
            raise ServerError(f"HTTP {status} from {url_out}", url=url_out, status_code=status)

        raise PermanentClientError(f"HTTP {status} from {url_out}", url=url_out, status_code=status)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> HttpxFetcher:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()


# Re-export FetchError for callers that want a single import path.
__all__ = ["DEFAULT_HEADERS", "DEFAULT_USER_AGENT", "FetchError", "HttpxFetcher"]
