# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import random
from datetime import UTC, datetime

import pytest

from application.ports.fetcher import (
    FetchRequest,
    FetchResponse,
    FetchTimeoutError,
    PermanentClientError,
    RateLimitedError,
    ServerError,
)
from infrastructure.fetcher.orchestrator import FetcherOrchestrator
from infrastructure.rate_limit import (
    CircuitOpenError,
    DomainRateLimiter,
    PerDomainCircuitBreaker,
)
from infrastructure.retry import RetryPolicy


class _ScriptedFetcher:
    """Returns successive scripted outcomes (Exception → raise, else return)."""

    def __init__(self, script: list[object]) -> None:
        self._script = list(script)
        self.calls: list[FetchRequest] = []

    async def fetch(self, request: FetchRequest) -> FetchResponse:
        self.calls.append(request)
        outcome = self._script.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, FetchResponse)
        return outcome

    async def aclose(self) -> None:
        return None


def _ok(url: str = "https://example.com/x") -> FetchResponse:
    return FetchResponse(
        url=url,
        status_code=200,
        headers={"content-type": "text/html"},
        body=b"hi",
        elapsed_s=0.01,
        fetched_at=datetime.now(tz=UTC),
    )


def _build_orchestrator(
    fetcher: _ScriptedFetcher,
    *,
    max_attempts: int = 3,
    breaker_threshold: int = 5,
) -> tuple[FetcherOrchestrator, list[float]]:
    delays: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        delays.append(seconds)

    orch = FetcherOrchestrator(
        fetcher=fetcher,
        rate_limiter=DomainRateLimiter(max_concurrent_per_domain=4, min_interval_s=0, jitter_s=0),
        circuit_breaker=PerDomainCircuitBreaker(failure_threshold=breaker_threshold, cooldown_s=10),
        retry_policy=RetryPolicy(
            max_attempts=max_attempts,
            base_delay_s=0.01,
            max_delay_s=0.5,
            jitter=False,
        ),
        sleep_fn=fake_sleep,
        rng=random.Random(0),
    )
    return orch, delays


async def test_first_attempt_success_no_sleep() -> None:
    f = _ScriptedFetcher([_ok()])
    orch, delays = _build_orchestrator(f)

    resp = await orch.fetch(FetchRequest(url="https://example.com/x"))

    assert resp.status_code == 200
    assert len(f.calls) == 1
    assert delays == []


async def test_retries_on_server_error_then_succeeds() -> None:
    f = _ScriptedFetcher(
        [
            ServerError("5xx", url="https://example.com/x", status_code=502),
            ServerError("5xx", url="https://example.com/x", status_code=502),
            _ok(),
        ]
    )
    orch, delays = _build_orchestrator(f, max_attempts=5)

    resp = await orch.fetch(FetchRequest(url="https://example.com/x"))

    assert resp.status_code == 200
    assert len(f.calls) == 3
    assert len(delays) == 2
    # Exponential w/o jitter: 0.01 then 0.02
    assert delays[0] == pytest.approx(0.01)
    assert delays[1] == pytest.approx(0.02)


async def test_gives_up_after_max_attempts() -> None:
    f = _ScriptedFetcher(
        [
            FetchTimeoutError("t", url="https://example.com/x"),
            FetchTimeoutError("t", url="https://example.com/x"),
            FetchTimeoutError("t", url="https://example.com/x"),
        ]
    )
    orch, delays = _build_orchestrator(f, max_attempts=3, breaker_threshold=10)

    with pytest.raises(FetchTimeoutError):
        await orch.fetch(FetchRequest(url="https://example.com/x"))

    assert len(f.calls) == 3
    assert len(delays) == 2  # sleep between attempts 1->2 and 2->3, not after final


async def test_permanent_client_error_does_not_retry() -> None:
    f = _ScriptedFetcher(
        [PermanentClientError("404", url="https://example.com/x", status_code=404)]
    )
    orch, delays = _build_orchestrator(f)

    with pytest.raises(PermanentClientError):
        await orch.fetch(FetchRequest(url="https://example.com/x"))

    assert len(f.calls) == 1
    assert delays == []


async def test_rate_limited_uses_retry_after() -> None:
    f = _ScriptedFetcher(
        [
            RateLimitedError("429", url="https://example.com/x", retry_after_s=0.42),
            _ok(),
        ]
    )
    orch, delays = _build_orchestrator(f, max_attempts=5)

    await orch.fetch(FetchRequest(url="https://example.com/x"))

    assert delays == [pytest.approx(0.42)]


async def test_circuit_open_short_circuits_without_calling_fetcher() -> None:
    # Pre-trip the circuit by causing 1 failure with threshold=1
    f = _ScriptedFetcher([ServerError("5xx", url="https://example.com/x", status_code=500)])
    orch, _delays = _build_orchestrator(f, max_attempts=1, breaker_threshold=1)

    with pytest.raises(ServerError):
        await orch.fetch(FetchRequest(url="https://example.com/x"))
    assert len(f.calls) == 1

    # Next call: circuit is OPEN, must raise CircuitOpenError WITHOUT invoking fetcher
    with pytest.raises(CircuitOpenError):
        await orch.fetch(FetchRequest(url="https://example.com/x"))
    assert len(f.calls) == 1  # unchanged
