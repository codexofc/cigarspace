# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""CurlCffiFetcher — IFetcher implementation backed by curl_cffi (L1 tier).

L1 is used when L0 (httpx) gets blocked by WAF / TLS fingerprinting
(Cloudflare, Akamai, …). curl_cffi reproduces the JA3 / TLS fingerprint
of a real browser via curl-impersonate, defeating most basic
fingerprint-based bot detections.

The default impersonation target is `chrome131` — a current, stable,
well-supported profile. It can be swapped per instance.
"""

from __future__ import annotations

import random
import time
from collections.abc import Sequence
from datetime import datetime, timezone

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import (
    ConnectionError as CurlConnectionError,
    RequestException as CurlRequestException,
    Timeout as CurlTimeout,
)

from application.ports.fetcher import (
    FetchRequest,
    FetchResponse,
    FetchTimeoutError,
    ForbiddenError,
    NetworkError,
    PermanentClientError,
    RateLimitedError,
    ServerError,
)
from infrastructure.fetcher.httpx_fetcher import DEFAULT_HEADERS

DEFAULT_IMPERSONATE = "chrome131"

# Pool of well-supported, current browser profiles for L1 rotation.
# All targets are present in curl_cffi >= 0.7.
DEFAULT_IMPERSONATE_POOL: tuple[str, ...] = (
    "chrome131",
    "chrome136",
    "chrome142",
    "firefox144",
    "safari260",
)


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


class CurlCffiFetcher:
    """IFetcher implementation using curl_cffi with browser TLS impersonation."""

    def __init__(
        self,
        *,
        impersonate: str = DEFAULT_IMPERSONATE,
        impersonate_pool: Sequence[str] | None = None,
        default_headers: dict[str, str] | None = None,
        max_connections: int = 50,
        verify_tls: bool = True,
        proxy_url: str | None = None,
        rng: random.Random | None = None,
    ) -> None:
        # Build a header set consistent with the impersonated browser.
        # We start from httpx defaults but DROP User-Agent — curl_cffi sets the
        # right one for the impersonated browser, and overriding it would break
        # the TLS+UA coherence.
        headers = dict(DEFAULT_HEADERS)
        headers.pop("User-Agent", None)
        if default_headers:
            headers.update(default_headers)
        self._default_headers = headers

        # impersonate_pool=None  → no rotation, always `impersonate`
        # impersonate_pool=[...] → pick uniformly at random per request
        self._impersonate = impersonate
        self._impersonate_pool: tuple[str, ...] | None = (
            tuple(impersonate_pool) if impersonate_pool else None
        )
        if self._impersonate_pool is not None and not self._impersonate_pool:
            raise ValueError("impersonate_pool must be non-empty when provided")
        self._rng = rng or random.Random()

        self._session = AsyncSession(
            impersonate=impersonate,
            max_clients=max_connections,
            verify=verify_tls,
            proxy=proxy_url,
        )

    def _pick_impersonate(self) -> str:
        if self._impersonate_pool is None:
            return self._impersonate
        return self._rng.choice(self._impersonate_pool)

    async def fetch(self, request: FetchRequest) -> FetchResponse:
        headers = {**self._default_headers, **request.headers}

        if request.proxy_url is not None:
            raise NotImplementedError(
                "Per-request proxy override is not supported on CurlCffiFetcher; "
                "construct a dedicated instance with proxy_url=... if needed."
            )

        # When we have a pool of impersonations, treat 403 as a likely
        # browser-fingerprint mismatch: retry with a different impersonate
        # before giving up. Bounded to len(pool) attempts so a real 403 stays
        # surfaced quickly.
        attempts = (
            list(self._impersonate_pool)
            if self._impersonate_pool is not None
            else [self._impersonate]
        )
        # Pick the order: first the random choice, then the remaining pool
        # in deterministic order so subsequent calls don't keep stumbling on
        # the same bad fingerprint twice in a row.
        first = self._pick_impersonate()
        ordered: list[str] = [first] + [imp for imp in attempts if imp != first]

        started = time.monotonic()
        last_403_url: str | None = None
        for impersonate in ordered:
            try:
                response = await self._session.request(
                    method=request.method,
                    url=request.url,
                    headers=headers,
                    data=request.body,
                    timeout=request.timeout_s,
                    allow_redirects=request.follow_redirects,
                    impersonate=impersonate,
                )
            except CurlTimeout as exc:
                raise FetchTimeoutError(str(exc), url=request.url) from exc
            except CurlConnectionError as exc:
                raise NetworkError(str(exc), url=request.url) from exc
            except CurlRequestException as exc:
                raise NetworkError(str(exc), url=request.url) from exc

            status = int(response.status_code)
            if status == 403 and len(ordered) > 1:
                last_403_url = str(response.url)
                continue
            break
        elapsed = time.monotonic() - started
        status = int(response.status_code)
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
                fetched_at=datetime.now(tz=timezone.utc),
            )

        if status == 429:
            raise RateLimitedError(
                f"HTTP 429 from {url_out}",
                url=url_out,
                retry_after_s=_parse_retry_after(headers_out.get("retry-after")),
            )
        if status == 403:
            raise ForbiddenError(
                f"HTTP 403 from {url_out} (all {len(ordered)} impersonate attempts blocked)",
                url=last_403_url or url_out,
            )
        if 500 <= status < 600:
            raise ServerError(f"HTTP {status} from {url_out}", url=url_out, status_code=status)

        raise PermanentClientError(f"HTTP {status} from {url_out}", url=url_out, status_code=status)

    async def aclose(self) -> None:
        await self._session.close()

    async def __aenter__(self) -> CurlCffiFetcher:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()
