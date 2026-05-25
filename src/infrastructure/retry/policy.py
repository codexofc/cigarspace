# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Retry policy — pure, deterministic given a seeded RNG.

The policy answers two questions:
- is *this* exception retriable?
- how long should we wait before attempt N?

Sleep itself is the orchestrator's responsibility; this module never
calls asyncio.sleep so it stays trivially unit-testable.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from application.ports.fetcher import (
    FetchError,
    FetchTimeoutError,
    ForbiddenError,
    NetworkError,
    RateLimitedError,
    ServerError,
)

_RETRIABLE_TYPES: tuple[type[FetchError], ...] = (
    FetchTimeoutError,
    NetworkError,
    RateLimitedError,
    ForbiddenError,
    ServerError,
)


def is_retriable(exc: BaseException) -> bool:
    return isinstance(exc, _RETRIABLE_TYPES)


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff with multiplicative jitter."""

    max_attempts: int = 3
    base_delay_s: float = 1.0
    max_delay_s: float = 60.0
    jitter: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay_s < 0:
            raise ValueError("base_delay_s must be >= 0")
        if self.max_delay_s < self.base_delay_s:
            raise ValueError("max_delay_s must be >= base_delay_s")

    def delay_for(
        self,
        attempt: int,
        exc: BaseException | None = None,
        *,
        rng: random.Random | None = None,
    ) -> float:
        """Delay before attempt N (N starting at 1).

        If exc is a RateLimitedError carrying Retry-After, honour it instead
        of computing the exponential delay.
        """

        if attempt < 1:
            raise ValueError("attempt must be >= 1")

        if isinstance(exc, RateLimitedError) and exc.retry_after_s is not None:
            return min(self.max_delay_s, max(0.0, exc.retry_after_s))

        # Exponential: base * 2^(attempt-1), capped
        delay = min(self.max_delay_s, self.base_delay_s * (2 ** (attempt - 1)))
        if self.jitter:
            r = rng if rng is not None else random
            delay *= 0.5 + r.random() * 0.5
        return delay
