# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""robots.txt fetcher + per-domain cache + access policy.

Uses urllib.robotparser (stdlib) for parsing — robust enough for our use
case and zero dep cost. We only ever fetch robots.txt over plain httpx
(no TLS impersonation needed) and cache the parser per domain.

Policy modes:
- "respect"  : disallow → RobotsBlockedError raised
- "log_only" : disallow logged but allowed through
- "ignore"   : robots.txt not fetched at all
"""

from __future__ import annotations

import asyncio
import time
from typing import Literal
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from application.ports.fetcher import FetchError
from infrastructure.observability.logging import get_logger

PolicyMode = Literal["respect", "log_only", "ignore"]


class RobotsBlockedError(FetchError):
    """Raised when a request is blocked by the target's robots.txt and the
    policy is set to respect it. Treat as PERMANENT — do not retry."""


class _CacheEntry:
    __slots__ = ("parser", "fetched_at", "fetch_error")

    def __init__(self, parser: RobotFileParser | None, fetch_error: str | None = None) -> None:
        self.parser = parser
        self.fetched_at = time.monotonic()
        self.fetch_error = fetch_error


class RobotsPolicy:
    """Async robots.txt enforcement with per-origin caching.

    Args:
        mode: respect | log_only | ignore
        cache_ttl_s: how long a parsed robots.txt is kept
        user_agent: UA reported when checking can_fetch()
        timeout_s: per-fetch timeout for robots.txt itself
        on_fetch_error: if robots.txt can't be retrieved (404/timeout),
            "allow" treats the site as wide open, "deny" blocks everything.
    """

    def __init__(
        self,
        *,
        mode: PolicyMode = "respect",
        cache_ttl_s: float = 3600.0,
        user_agent: str = "cigars-scrapper",
        timeout_s: float = 10.0,
        on_fetch_error: Literal["allow", "deny"] = "allow",
        overrides: dict[str, PolicyMode] | None = None,
    ) -> None:
        self._mode: PolicyMode = mode
        self._ttl = cache_ttl_s
        self._ua = user_agent
        self._timeout = timeout_s
        self._on_error = on_fetch_error
        self._overrides = dict(overrides or {})
        self._cache: dict[str, _CacheEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._log = get_logger("robots")

    def _effective_mode(self, host: str) -> PolicyMode:
        return self._overrides.get(host, self._mode)

    def _lock(self, host: str) -> asyncio.Lock:
        lock = self._locks.get(host)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[host] = lock
        return lock

    async def _load(self, scheme: str, host: str) -> _CacheEntry:
        cached = self._cache.get(host)
        if cached is not None and (time.monotonic() - cached.fetched_at) < self._ttl:
            return cached

        async with self._lock(host):
            cached = self._cache.get(host)
            if cached is not None and (time.monotonic() - cached.fetched_at) < self._ttl:
                return cached

            robots_url = f"{scheme}://{host}/robots.txt"
            parser = RobotFileParser()
            parser.set_url(robots_url)

            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    r = await client.get(robots_url, follow_redirects=True)
                if r.status_code == 200:
                    parser.parse(r.text.splitlines())
                    entry = _CacheEntry(parser=parser)
                elif r.status_code in (401, 403):
                    # RFC 9309: 401/403 → treat as fully disallowed.
                    parser.disallow_all = True  # type: ignore[attr-defined]
                    entry = _CacheEntry(parser=parser)
                elif 400 <= r.status_code < 500:
                    # 404 etc. → no robots = fully allowed
                    parser.allow_all = True  # type: ignore[attr-defined]
                    entry = _CacheEntry(parser=parser)
                else:
                    # 5xx or unexpected — treat per policy on_fetch_error
                    entry = _CacheEntry(parser=None, fetch_error=f"http_{r.status_code}")
            except Exception as exc:  # noqa: BLE001
                entry = _CacheEntry(parser=None, fetch_error=str(exc))

            self._cache[host] = entry
            return entry

    async def is_allowed(self, url: str) -> bool:
        """Returns True if the URL is allowed under the active policy.

        - mode 'ignore'  : always True
        - mode 'respect' : honour robots.txt strictly
        - mode 'log_only': always True but logs a warning on disallow
        """

        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return True

        mode = self._effective_mode(host)
        if mode == "ignore":
            return True

        entry = await self._load(parsed.scheme or "https", host)
        if entry.parser is None:
            self._log.warning(
                "robots_fetch_unavailable",
                host=host,
                error=entry.fetch_error,
                policy=self._on_error,
            )
            return self._on_error == "allow"

        allowed = entry.parser.can_fetch(self._ua, url)
        if not allowed:
            if mode == "log_only":
                self._log.warning("robots_disallow_logged_only", host=host, url=url)
                return True
            self._log.info("robots_disallow", host=host, url=url)
        return allowed

    async def assert_allowed(self, url: str) -> None:
        """Raise RobotsBlockedError if the URL is not allowed."""

        if not await self.is_allowed(url):
            raise RobotsBlockedError(f"robots.txt disallows {url}", url=url)
