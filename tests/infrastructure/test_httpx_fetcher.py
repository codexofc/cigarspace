# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import httpx
import pytest
import respx

from application.ports.fetcher import (
    FetchRequest,
    FetchTimeoutError,
    ForbiddenError,
    NetworkError,
    PermanentClientError,
    RateLimitedError,
    ServerError,
)
from infrastructure.fetcher.httpx_fetcher import HttpxFetcher


@respx.mock
async def test_fetch_ok_returns_response() -> None:
    respx.get("https://example.com/cigars/cohiba").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b"<html>Cohiba</html>",
        )
    )

    async with HttpxFetcher() as fetcher:
        resp = await fetcher.fetch(FetchRequest(url="https://example.com/cigars/cohiba"))

    assert resp.status_code == 200
    assert resp.body == b"<html>Cohiba</html>"
    assert "Cohiba" in resp.text
    assert resp.elapsed_s >= 0
    assert resp.fetched_at is not None
    assert resp.headers.get("content-type", "").startswith("text/html")


@respx.mock
async def test_fetch_429_raises_rate_limited_with_retry_after() -> None:
    respx.get("https://example.com/x").mock(
        return_value=httpx.Response(429, headers={"retry-after": "12"})
    )

    async with HttpxFetcher() as fetcher:
        with pytest.raises(RateLimitedError) as ei:
            await fetcher.fetch(FetchRequest(url="https://example.com/x"))

    assert ei.value.retry_after_s == 12.0


@respx.mock
async def test_fetch_403_raises_forbidden() -> None:
    respx.get("https://example.com/x").mock(return_value=httpx.Response(403))
    async with HttpxFetcher() as fetcher:
        with pytest.raises(ForbiddenError):
            await fetcher.fetch(FetchRequest(url="https://example.com/x"))


@respx.mock
async def test_fetch_404_raises_permanent_client_error() -> None:
    respx.get("https://example.com/x").mock(return_value=httpx.Response(404))
    async with HttpxFetcher() as fetcher:
        with pytest.raises(PermanentClientError) as ei:
            await fetcher.fetch(FetchRequest(url="https://example.com/x"))

    assert ei.value.status_code == 404


@respx.mock
async def test_fetch_5xx_raises_server_error() -> None:
    respx.get("https://example.com/x").mock(return_value=httpx.Response(503))
    async with HttpxFetcher() as fetcher:
        with pytest.raises(ServerError) as ei:
            await fetcher.fetch(FetchRequest(url="https://example.com/x"))

    assert ei.value.status_code == 503


@respx.mock
async def test_timeout_maps_to_fetch_timeout_error() -> None:
    respx.get("https://example.com/x").mock(side_effect=httpx.ReadTimeout("slow"))
    async with HttpxFetcher() as fetcher:
        with pytest.raises(FetchTimeoutError):
            await fetcher.fetch(FetchRequest(url="https://example.com/x", timeout_s=1.0))


@respx.mock
async def test_connect_error_maps_to_network_error() -> None:
    respx.get("https://example.com/x").mock(side_effect=httpx.ConnectError("nope"))
    async with HttpxFetcher() as fetcher:
        with pytest.raises(NetworkError):
            await fetcher.fetch(FetchRequest(url="https://example.com/x"))


@respx.mock
async def test_default_headers_applied() -> None:
    route = respx.get("https://example.com/x").mock(return_value=httpx.Response(200, content=b""))
    async with HttpxFetcher() as fetcher:
        await fetcher.fetch(FetchRequest(url="https://example.com/x"))

    sent = route.calls.last.request
    assert "User-Agent" in sent.headers
    assert "Mozilla" in sent.headers["User-Agent"]
    assert "Accept-Language" in sent.headers


@respx.mock
async def test_custom_headers_override_defaults() -> None:
    route = respx.get("https://example.com/x").mock(return_value=httpx.Response(200, content=b""))
    async with HttpxFetcher() as fetcher:
        await fetcher.fetch(
            FetchRequest(
                url="https://example.com/x",
                headers={"User-Agent": "MyBot/1.0", "X-Trace": "abc"},
            )
        )

    sent = route.calls.last.request
    assert sent.headers["User-Agent"] == "MyBot/1.0"
    assert sent.headers["X-Trace"] == "abc"


async def test_per_request_proxy_is_rejected() -> None:
    async with HttpxFetcher() as fetcher:
        with pytest.raises(NotImplementedError):
            await fetcher.fetch(
                FetchRequest(url="https://example.com/x", proxy_url="http://proxy:8888")
            )
