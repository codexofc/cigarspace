# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from infrastructure.fetcher.browser_fetcher import BrowserFetcher
from infrastructure.fetcher.curl_cffi_fetcher import (
    DEFAULT_IMPERSONATE,
    DEFAULT_IMPERSONATE_POOL,
    CurlCffiFetcher,
)
from infrastructure.fetcher.httpx_fetcher import (
    DEFAULT_HEADERS,
    DEFAULT_USER_AGENT,
    HttpxFetcher,
)
from infrastructure.fetcher.orchestrator import FetcherOrchestrator
from infrastructure.fetcher.robots import RobotsBlockedError, RobotsPolicy
from infrastructure.fetcher.soft_ban import SoftBanDetector, SoftBanSignal
from infrastructure.fetcher.tiered import TieredFetcher

__all__ = [
    "DEFAULT_HEADERS",
    "DEFAULT_IMPERSONATE",
    "DEFAULT_IMPERSONATE_POOL",
    "DEFAULT_USER_AGENT",
    "BrowserFetcher",
    "CurlCffiFetcher",
    "FetcherOrchestrator",
    "HttpxFetcher",
    "RobotsBlockedError",
    "RobotsPolicy",
    "SoftBanDetector",
    "SoftBanSignal",
    "TieredFetcher",
]
