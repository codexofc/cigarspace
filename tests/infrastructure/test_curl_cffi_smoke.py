# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Real-network smoke tests for CurlCffiFetcher.

These verify that the Chrome TLS impersonation actually defeats the WAF
on representative protected sites (FR/CH cigar merchants). Marked
`network` so they are skipped by `make test` (which excludes them); run
with `make test-all` or `uv run pytest -m network`.
"""

from __future__ import annotations

import pytest

from application.ports.fetcher import FetchRequest
from infrastructure.fetcher.curl_cffi_fetcher import CurlCffiFetcher
from infrastructure.fetcher.httpx_fetcher import HttpxFetcher
from infrastructure.fetcher.tiered import TieredFetcher

pytestmark = pytest.mark.network


WAF_PROTECTED_URLS = [
    "https://mistercigar.com/",
    "https://cigarpassion.ch/",
]


@pytest.mark.parametrize("url", WAF_PROTECTED_URLS)
async def test_curl_cffi_defeats_waf(url: str) -> None:
    async with CurlCffiFetcher() as f:
        resp = await f.fetch(FetchRequest(url=url, timeout_s=30))
    assert resp.status_code == 200
    assert len(resp.body) > 10_000  # real page, not a blocker stub


@pytest.mark.parametrize("url", WAF_PROTECTED_URLS)
async def test_tiered_fetcher_serves_real_page(url: str) -> None:
    """Either L0 already passes (some WAFs accept a plausible UA), or it
    gets a 403 and escalation to L1 succeeds. Both outcomes are valid;
    what matters is that the caller eventually receives the real page."""
    async with HttpxFetcher() as l0, CurlCffiFetcher() as l1:
        tiered = TieredFetcher.with_default_pipeline(l0=l0, l1=l1)
        resp = await tiered.fetch(FetchRequest(url=url, timeout_s=30))

    assert resp.status_code == 200
    assert len(resp.body) > 10_000
    assert tiered.tier_for(url) in {"l0", "l1"}
