# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Smoke tests for BrowserFetcher (L4 — patched Chromium via patchright).

Marked `network`. They launch a real headless Chromium, so each test
adds ~2-3 seconds. Run with `make test-network`.

Requires `patchright install chromium` to have been executed once
(usually via `make patchright-install`).
"""

from __future__ import annotations

import pytest

from application.ports.fetcher import FetchRequest
from infrastructure.fetcher.browser_fetcher import BrowserFetcher

pytestmark = pytest.mark.network


async def test_browser_fetches_simple_page() -> None:
    async with BrowserFetcher(max_concurrent_contexts=1) as f:
        resp = await f.fetch(FetchRequest(url="https://api.ipify.org", timeout_s=30))

    assert resp.status_code == 200
    # api.ipify.org returns the IP wrapped in minimal HTML when fetched by a browser
    assert b"." in resp.body  # contains an IPv4 address
    assert resp.elapsed_s > 0


async def test_browser_fetches_mistercigar_with_real_render() -> None:
    """Confirms L4 returns a fully-rendered page, not a blocker stub."""
    async with BrowserFetcher(max_concurrent_contexts=1) as f:
        resp = await f.fetch(FetchRequest(url="https://mistercigar.com/", timeout_s=45))

    assert resp.status_code == 200
    # Real page should weigh a few hundred KB
    assert len(resp.body) > 100_000


async def test_browser_rejects_non_get() -> None:
    async with BrowserFetcher(max_concurrent_contexts=1) as f:
        with pytest.raises(NotImplementedError):
            await f.fetch(FetchRequest(url="https://api.ipify.org", method="POST", timeout_s=10))


async def test_browser_rejects_per_request_proxy() -> None:
    async with BrowserFetcher(max_concurrent_contexts=1) as f:
        with pytest.raises(NotImplementedError):
            await f.fetch(
                FetchRequest(
                    url="https://api.ipify.org",
                    proxy_url="http://proxy:8888",
                    timeout_s=10,
                )
            )
