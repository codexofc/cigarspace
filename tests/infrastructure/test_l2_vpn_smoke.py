# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Smoke tests for L2 (ProtonVPN via gluetun).

These tests require:
- the `gluetun` sidecar running and healthy: `make vpn-up`
- a valid ProtonVPN WireGuard config in .env

Skipped automatically if the proxy is unreachable. Marked `network`.
"""

from __future__ import annotations

import httpx
import pytest

from application.ports.fetcher import FetchRequest
from infrastructure.fetcher.curl_cffi_fetcher import CurlCffiFetcher

pytestmark = pytest.mark.network

L2_PROXY = "http://127.0.0.1:8888"


def _l2_available() -> bool:
    try:
        r = httpx.get("https://api.ipify.org", proxy=L2_PROXY, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(
        not _l2_available(), reason="gluetun L2 proxy not reachable on 127.0.0.1:8888"
    ),
]


async def test_l2_changes_outbound_ip() -> None:
    """Through the VPN, the outbound IP must differ from the direct one."""

    direct = httpx.get("https://api.ipify.org", timeout=10).text.strip()
    async with CurlCffiFetcher(proxy_url=L2_PROXY) as f:
        resp = await f.fetch(FetchRequest(url="https://api.ipify.org", timeout_s=15))
    via_vpn = resp.body.decode().strip()

    assert direct != via_vpn, f"VPN IP {via_vpn} should differ from direct {direct}"


async def test_l2_defeats_waf_mistercigar() -> None:
    async with CurlCffiFetcher(proxy_url=L2_PROXY) as f:
        resp = await f.fetch(FetchRequest(url="https://mistercigar.com/", timeout_s=30))
    assert resp.status_code == 200
    assert len(resp.body) > 100_000


# NOTE: a similar test on cigarpassion.ch was intentionally removed.
# Their Cloudflare instance is more aggressive toward Proton Free shared
# exit IPs (other free users push them onto the suspect list); the test
# was flaky depending on recent neighbour activity. cigarpassion.ch is
# still reachable via L1 (direct curl_cffi), which is what TieredFetcher
# will pick first anyway — L2 is only triggered when L1 also fails.
