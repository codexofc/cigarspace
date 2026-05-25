# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""FetcherOrchestrator — composes the moving parts behind a single fetch.

Pipeline applied per request:
    rate_limit.slot(url)
        circuit_breaker.guard(url)
            fetcher.fetch(request)
                ⤷ on retriable error: retry_policy.delay_for(...) + asyncio.sleep
                ⤷ on circuit-open / permanent-client error: raise immediately

The orchestrator is the single object that application use cases hold a
reference to; everything below is wiring detail.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable

from application.ports.fetcher import (
    FetchError,
    FetchRequest,
    FetchResponse,
    IFetcher,
    PermanentClientError,
)
from infrastructure.observability.logging import get_logger
from infrastructure.rate_limit import (
    CircuitOpenError,
    DomainRateLimiter,
    PerDomainCircuitBreaker,
    extract_domain,
)
from infrastructure.retry import RetryPolicy, is_retriable

SleepFn = Callable[[float], Awaitable[None]]


class FetcherOrchestrator:
    """Assembles fetcher + rate limiter + circuit breaker + retry policy."""

    def __init__(
        self,
        *,
        fetcher: IFetcher,
        rate_limiter: DomainRateLimiter | None = None,
        circuit_breaker: PerDomainCircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        sleep_fn: SleepFn = asyncio.sleep,
        rng: random.Random | None = None,
    ) -> None:
        self._fetcher = fetcher
        self._rate_limiter = rate_limiter or DomainRateLimiter()
        self._breaker = circuit_breaker or PerDomainCircuitBreaker()
        self._retry = retry_policy or RetryPolicy()
        self._sleep = sleep_fn
        self._rng = rng or random.Random()
        self._log = get_logger("fetcher")

    async def fetch(self, request: FetchRequest) -> FetchResponse:
        domain = extract_domain(request.url)
        last_exc: BaseException | None = None

        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                async with self._rate_limiter.slot(request.url):
                    async with self._breaker.guard(request.url):
                        response = await self._fetcher.fetch(request)
                self._log.info(
                    "fetch_ok",
                    domain=domain,
                    url=request.url,
                    status=response.status_code,
                    elapsed_s=round(response.elapsed_s, 3),
                    attempt=attempt,
                )
                return response
            except CircuitOpenError as exc:
                self._log.warning("fetch_circuit_open", domain=domain, url=request.url)
                raise exc
            except PermanentClientError as exc:
                self._log.warning(
                    "fetch_permanent",
                    domain=domain,
                    url=request.url,
                    status=exc.status_code,
                )
                raise
            except FetchError as exc:
                last_exc = exc
                if not is_retriable(exc) or attempt >= self._retry.max_attempts:
                    self._log.warning(
                        "fetch_failed",
                        domain=domain,
                        url=request.url,
                        attempts=attempt,
                        error=type(exc).__name__,
                    )
                    raise
                delay = self._retry.delay_for(attempt, exc, rng=self._rng)
                self._log.info(
                    "fetch_retry",
                    domain=domain,
                    url=request.url,
                    attempt=attempt,
                    delay_s=round(delay, 3),
                    error=type(exc).__name__,
                )
                await self._sleep(delay)

        # Defensive: loop should have either returned or raised.
        assert last_exc is not None
        raise last_exc

    async def aclose(self) -> None:
        await self._fetcher.aclose()
