# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import asyncio
import time

import pytest

from application.ports.fetcher import ServerError
from infrastructure.rate_limit.circuit_breaker import (
    CircuitOpenError,
    CircuitState,
    PerDomainCircuitBreaker,
)


def test_invalid_args_rejected() -> None:
    with pytest.raises(ValueError):
        PerDomainCircuitBreaker(failure_threshold=0)
    with pytest.raises(ValueError):
        PerDomainCircuitBreaker(cooldown_s=-1)


async def test_closed_state_passes_requests() -> None:
    breaker = PerDomainCircuitBreaker(failure_threshold=3, cooldown_s=1)
    async with breaker.guard("https://x.example.com/"):
        pass
    assert breaker.state_of("https://x.example.com/") is CircuitState.CLOSED


async def test_opens_after_threshold() -> None:
    breaker = PerDomainCircuitBreaker(failure_threshold=3, cooldown_s=10)

    for _ in range(3):
        with pytest.raises(ServerError):
            async with breaker.guard("https://x.example.com/"):
                raise ServerError("5xx", url="https://x.example.com/", status_code=500)

    assert breaker.state_of("https://x.example.com/") is CircuitState.OPEN


async def test_rejects_when_open() -> None:
    breaker = PerDomainCircuitBreaker(failure_threshold=1, cooldown_s=10)
    with pytest.raises(ServerError):
        async with breaker.guard("https://x.example.com/"):
            raise ServerError("5xx", url="https://x.example.com/", status_code=500)

    with pytest.raises(CircuitOpenError):
        async with breaker.guard("https://x.example.com/"):
            pass  # pragma: no cover — should not be entered


async def test_half_open_then_closed_on_success() -> None:
    breaker = PerDomainCircuitBreaker(failure_threshold=1, cooldown_s=0.05)
    with pytest.raises(ServerError):
        async with breaker.guard("https://x.example.com/"):
            raise ServerError("5xx", url="https://x.example.com/", status_code=500)

    await asyncio.sleep(0.06)

    async with breaker.guard("https://x.example.com/"):
        pass

    assert breaker.state_of("https://x.example.com/") is CircuitState.CLOSED


async def test_half_open_failure_returns_to_open() -> None:
    breaker = PerDomainCircuitBreaker(failure_threshold=1, cooldown_s=0.05)
    with pytest.raises(ServerError):
        async with breaker.guard("https://x.example.com/"):
            raise ServerError("5xx", url="https://x.example.com/", status_code=500)

    await asyncio.sleep(0.06)

    with pytest.raises(ServerError):
        async with breaker.guard("https://x.example.com/"):
            raise ServerError("5xx2", url="https://x.example.com/", status_code=500)

    # Probe failed -> re-opened, and the cooldown clock should have reset
    assert breaker.state_of("https://x.example.com/") is CircuitState.OPEN


async def test_success_resets_failure_counter() -> None:
    breaker = PerDomainCircuitBreaker(failure_threshold=3, cooldown_s=10)

    for _ in range(2):
        with pytest.raises(ServerError):
            async with breaker.guard("https://x.example.com/"):
                raise ServerError("5xx", url="https://x.example.com/")

    # One success — counter should reset, breaker stays CLOSED
    async with breaker.guard("https://x.example.com/"):
        pass
    assert breaker.state_of("https://x.example.com/") is CircuitState.CLOSED

    # Two more failures must NOT yet trigger OPEN (counter was reset)
    for _ in range(2):
        with pytest.raises(ServerError):
            async with breaker.guard("https://x.example.com/"):
                raise ServerError("5xx", url="https://x.example.com/")

    assert breaker.state_of("https://x.example.com/") is CircuitState.CLOSED


async def test_domains_isolated() -> None:
    breaker = PerDomainCircuitBreaker(failure_threshold=1, cooldown_s=10)

    with pytest.raises(ServerError):
        async with breaker.guard("https://a.example.com/"):
            raise ServerError("5xx", url="https://a.example.com/")

    assert breaker.state_of("https://a.example.com/") is CircuitState.OPEN
    assert breaker.state_of("https://b.example.com/") is CircuitState.CLOSED

    # Domain B unaffected
    async with breaker.guard("https://b.example.com/"):
        pass
    _ = time.monotonic()  # keep import used
