# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Per-domain rate limiting.

Two constraints applied together for each outbound request:
- a semaphore caps the number of *concurrent* requests per domain,
- a minimum interval (with jitter) caps the *rate* of requests per domain.

Both default to conservative values; tune per source in config later.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlparse


def extract_domain(url: str) -> str:
    """Lowercased hostname or empty string."""

    return (urlparse(url).hostname or "").lower()


class DomainRateLimiter:
    """Concurrent-request cap + min-interval enforcement, scoped per domain."""

    def __init__(
        self,
        *,
        max_concurrent_per_domain: int = 4,
        min_interval_s: float = 0.5,
        jitter_s: float = 0.5,
    ) -> None:
        if max_concurrent_per_domain < 1:
            raise ValueError("max_concurrent_per_domain must be >= 1")
        if min_interval_s < 0:
            raise ValueError("min_interval_s must be >= 0")
        if jitter_s < 0:
            raise ValueError("jitter_s must be >= 0")

        self._max_concurrent = max_concurrent_per_domain
        self._min_interval = min_interval_s
        self._jitter = jitter_s
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._last_release: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _semaphore_for(self, domain: str) -> asyncio.Semaphore:
        sem = self._semaphores.get(domain)
        if sem is None:
            sem = asyncio.Semaphore(self._max_concurrent)
            self._semaphores[domain] = sem
        return sem

    def _lock_for(self, domain: str) -> asyncio.Lock:
        lock = self._locks.get(domain)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[domain] = lock
        return lock

    @asynccontextmanager
    async def slot(self, url: str) -> AsyncIterator[None]:
        """Acquire a slot for the URL's domain. Releases on exit.

        The min-interval is enforced AFTER a request completes (release timestamp),
        so back-pressure builds up naturally without sleeping inside the lock.
        """

        domain = extract_domain(url)
        sem = self._semaphore_for(domain)
        lock = self._lock_for(domain)

        await sem.acquire()
        try:
            async with lock:
                last = self._last_release.get(domain)
                if last is not None and self._min_interval > 0:
                    delay = self._min_interval - (time.monotonic() - last)
                    if self._jitter > 0:
                        delay += random.uniform(0, self._jitter)
                    if delay > 0:
                        await asyncio.sleep(delay)
            yield
        finally:
            self._last_release[domain] = time.monotonic()
            sem.release()
