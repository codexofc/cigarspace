# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Per-domain circuit breaker.

States: CLOSED → OPEN → HALF_OPEN → CLOSED.

- CLOSED: requests pass through. Failures increment a counter; reaching
  the threshold flips the state to OPEN.
- OPEN: all requests are rejected with CircuitOpenError until cooldown_s
  has elapsed since the trip; first probe after that moves to HALF_OPEN.
- HALF_OPEN: a single trial request is allowed; on success the state
  returns to CLOSED, on failure it goes back to OPEN.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import StrEnum

from application.ports.fetcher import FetchError
from infrastructure.rate_limit.domain_limiter import extract_domain


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(FetchError):
    """Raised when a circuit is OPEN and the request is rejected pre-flight."""


@dataclass
class _DomainState:
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at: float = 0.0


class PerDomainCircuitBreaker:
    """Independent breaker per domain.

    Args:
        failure_threshold: consecutive failures before tripping
        cooldown_s: time to wait before allowing a probe
    """

    def __init__(self, *, failure_threshold: int = 5, cooldown_s: float = 30.0) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if cooldown_s < 0:
            raise ValueError("cooldown_s must be >= 0")
        self._threshold = failure_threshold
        self._cooldown = cooldown_s
        self._states: dict[str, _DomainState] = {}

    def _state_for(self, domain: str) -> _DomainState:
        st = self._states.get(domain)
        if st is None:
            st = _DomainState()
            self._states[domain] = st
        return st

    def state_of(self, url: str) -> CircuitState:
        return self._state_for(extract_domain(url)).state

    def _check(self, domain: str, now: float) -> None:
        st = self._state_for(domain)
        if st.state is CircuitState.OPEN:
            if now - st.opened_at >= self._cooldown:
                st.state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError(f"Circuit OPEN for domain {domain!r}")

    def _on_success(self, domain: str) -> None:
        st = self._state_for(domain)
        st.state = CircuitState.CLOSED
        st.consecutive_failures = 0
        st.opened_at = 0.0

    def _on_failure(self, domain: str, now: float) -> None:
        st = self._state_for(domain)
        if st.state is CircuitState.HALF_OPEN:
            # Probe failed → re-open without resetting cooldown clock
            st.state = CircuitState.OPEN
            st.opened_at = now
            return
        st.consecutive_failures += 1
        if st.consecutive_failures >= self._threshold:
            st.state = CircuitState.OPEN
            st.opened_at = now

    @asynccontextmanager
    async def guard(self, url: str) -> AsyncIterator[None]:
        """Pre-flight check + post-flight state update.

        Raises CircuitOpenError before yielding if the circuit is OPEN.
        On exit, success closes the breaker; any FetchError counts as a
        failure (CircuitOpenError itself does not — it never reaches here).
        """

        domain = extract_domain(url)
        now = time.monotonic()
        self._check(domain, now)
        try:
            yield
        except FetchError:
            self._on_failure(domain, time.monotonic())
            raise
        else:
            self._on_success(domain)
