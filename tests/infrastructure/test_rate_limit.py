# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import asyncio
import time

import pytest

from infrastructure.rate_limit.domain_limiter import DomainRateLimiter, extract_domain


def test_extract_domain_basic() -> None:
    assert extract_domain("https://www.cigaraficionado.com/path?q=1") == "www.cigaraficionado.com"
    assert extract_domain("HTTP://CigarsDirect.COM/foo") == "cigarsdirect.com"
    assert extract_domain("malformed") == ""


def test_invalid_args_rejected() -> None:
    with pytest.raises(ValueError):
        DomainRateLimiter(max_concurrent_per_domain=0)
    with pytest.raises(ValueError):
        DomainRateLimiter(min_interval_s=-1)
    with pytest.raises(ValueError):
        DomainRateLimiter(jitter_s=-1)


async def test_concurrency_cap_per_domain() -> None:
    limiter = DomainRateLimiter(max_concurrent_per_domain=2, min_interval_s=0, jitter_s=0)
    in_flight = 0
    peak = 0
    lock = asyncio.Lock()

    async def worker() -> None:
        nonlocal in_flight, peak
        async with limiter.slot("https://example.com/x"):
            async with lock:
                in_flight += 1
                peak = max(peak, in_flight)
            await asyncio.sleep(0.05)
            async with lock:
                in_flight -= 1

    await asyncio.gather(*(worker() for _ in range(8)))
    assert peak == 2


async def test_min_interval_enforced() -> None:
    limiter = DomainRateLimiter(max_concurrent_per_domain=1, min_interval_s=0.1, jitter_s=0)

    start = time.monotonic()
    for _ in range(3):
        async with limiter.slot("https://example.com/x"):
            pass
    elapsed = time.monotonic() - start

    # 3 acquisitions, 2 inter-request gaps of >= 0.1s
    assert elapsed >= 0.2


async def test_domains_are_independent() -> None:
    limiter = DomainRateLimiter(max_concurrent_per_domain=1, min_interval_s=0.2, jitter_s=0)

    # First slot on domain A — primes its timer
    async with limiter.slot("https://a.example.com/"):
        pass

    # Slot on domain B should NOT wait
    start = time.monotonic()
    async with limiter.slot("https://b.example.com/"):
        pass
    assert time.monotonic() - start < 0.05
