# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""BrowserFetcher — IFetcher implementation backed by patchright (L4 tier).

Patchright is a patched fork of Playwright that defeats advanced bot
detection at the CDP level (Runtime.enable leak, navigator.webdriver,
shadow DOM, etc.). It runs a real headless Chromium, so it's expensive
(150-300 MB/context, 1-5s per page) — reserve it for sites where every
lower tier (L0 httpx, L1 curl_cffi, L2 ProtonVPN) fails.

A single Browser is shared across requests; each `fetch()` opens a
disposable Context to keep cookies/storage isolated. Concurrency is
capped by an asyncio.Semaphore so the OS doesn't OOM.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

from patchright.async_api import (
    Error as PatchrightError,
    Playwright,
    TimeoutError as PatchrightTimeout,
    async_playwright,
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


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


class BrowserFetcher:
    """IFetcher implementation using patchright (patched Playwright) Chromium."""

    def __init__(
        self,
        *,
        headless: bool = True,
        max_concurrent_contexts: int = 2,
        proxy_url: str | None = None,
        default_headers: dict[str, str] | None = None,
        wait_until: str = "domcontentloaded",
    ) -> None:
        if max_concurrent_contexts < 1:
            raise ValueError("max_concurrent_contexts must be >= 1")
        self._headless = headless
        self._proxy_url = proxy_url
        self._default_headers = dict(default_headers or {})
        self._wait_until = wait_until
        self._sem = asyncio.Semaphore(max_concurrent_contexts)
        self._playwright: Playwright | None = None
        self._browser: Any = None
        self._start_lock = asyncio.Lock()

    async def _ensure_started(self) -> None:
        if self._browser is not None:
            return
        async with self._start_lock:
            if self._browser is not None:
                return
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless,
                # Standard hardening; patchright already adds its own anti-detection args.
                args=["--disable-dev-shm-usage", "--no-sandbox"],
            )

    async def fetch(self, request: FetchRequest) -> FetchResponse:
        if request.method.upper() != "GET":
            raise NotImplementedError(
                "BrowserFetcher only supports GET; use a lower-tier fetcher for other methods."
            )
        if request.proxy_url is not None:
            raise NotImplementedError(
                "Per-request proxy override is not supported on BrowserFetcher; "
                "construct a dedicated instance with proxy_url=... if needed."
            )

        await self._ensure_started()
        assert self._browser is not None

        headers = {**self._default_headers, **request.headers}

        context_kwargs: dict[str, Any] = {}
        if self._proxy_url is not None:
            context_kwargs["proxy"] = {"server": self._proxy_url}

        async with self._sem:
            context = await self._browser.new_context(**context_kwargs)
            try:
                if headers:
                    await context.set_extra_http_headers(headers)
                page = await context.new_page()

                started = time.monotonic()
                try:
                    response = await page.goto(
                        request.url,
                        timeout=request.timeout_s * 1000,  # ms
                        wait_until=self._wait_until,
                    )
                except PatchrightTimeout as exc:
                    raise FetchTimeoutError(str(exc), url=request.url) from exc
                except PatchrightError as exc:
                    raise NetworkError(str(exc), url=request.url) from exc

                if response is None:
                    # data: / about: navigations — treat as a soft failure
                    raise NetworkError(
                        "no HTTP response (possibly navigation to non-HTTP scheme)",
                        url=request.url,
                    )

                elapsed = time.monotonic() - started
                status = int(response.status)
                final_url = page.url

                # Rendered HTML after JS execution
                try:
                    body_text = await page.content()
                except PatchrightError as exc:
                    raise NetworkError(f"content() failed: {exc}", url=request.url) from exc

                body = body_text.encode("utf-8", errors="replace")
                headers_out = {k.lower(): v for k, v in (await response.all_headers()).items()}

                if 200 <= status < 400:
                    return FetchResponse(
                        url=final_url,
                        status_code=status,
                        headers=headers_out,
                        body=body,
                        elapsed_s=elapsed,
                        fetched_at=datetime.now(tz=timezone.utc),
                    )

                if status == 429:
                    raise RateLimitedError(
                        f"HTTP 429 from {final_url}",
                        url=final_url,
                        retry_after_s=_parse_retry_after(headers_out.get("retry-after")),
                    )
                if status == 403:
                    raise ForbiddenError(f"HTTP 403 from {final_url}", url=final_url)
                if 500 <= status < 600:
                    raise ServerError(
                        f"HTTP {status} from {final_url}",
                        url=final_url,
                        status_code=status,
                    )

                raise PermanentClientError(
                    f"HTTP {status} from {final_url}", url=final_url, status_code=status
                )
            finally:
                await context.close()

    async def aclose(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def __aenter__(self) -> BrowserFetcher:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()
