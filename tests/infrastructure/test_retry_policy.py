# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import random

import pytest

from application.ports.fetcher import (
    FetchTimeoutError,
    NetworkError,
    PermanentClientError,
    RateLimitedError,
    ServerError,
)
from infrastructure.retry.policy import RetryPolicy, is_retriable


def test_invalid_args_rejected() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(base_delay_s=-1)
    with pytest.raises(ValueError):
        RetryPolicy(base_delay_s=10, max_delay_s=5)


def test_is_retriable_for_known_errors() -> None:
    assert is_retriable(FetchTimeoutError("t"))
    assert is_retriable(NetworkError("n"))
    assert is_retriable(ServerError("5xx", status_code=500))
    assert is_retriable(RateLimitedError("429"))


def test_is_not_retriable_for_permanent_errors() -> None:
    assert not is_retriable(PermanentClientError("404", status_code=404))
    assert not is_retriable(ValueError("not a fetch error"))


def test_delay_without_jitter_is_exponential() -> None:
    policy = RetryPolicy(max_attempts=5, base_delay_s=1, max_delay_s=60, jitter=False)
    assert policy.delay_for(1) == 1.0
    assert policy.delay_for(2) == 2.0
    assert policy.delay_for(3) == 4.0
    assert policy.delay_for(4) == 8.0


def test_delay_caps_at_max() -> None:
    policy = RetryPolicy(max_attempts=10, base_delay_s=1, max_delay_s=8, jitter=False)
    assert policy.delay_for(5) == 8.0  # would be 16 without cap
    assert policy.delay_for(10) == 8.0


def test_delay_with_jitter_bounded() -> None:
    policy = RetryPolicy(max_attempts=5, base_delay_s=1, max_delay_s=60, jitter=True)
    rng = random.Random(42)
    for _ in range(50):
        d = policy.delay_for(3, rng=rng)
        # 4.0 * [0.5, 1.0] = [2.0, 4.0]
        assert 2.0 <= d <= 4.0


def test_rate_limited_honours_retry_after() -> None:
    policy = RetryPolicy(max_attempts=5, base_delay_s=1, max_delay_s=60, jitter=False)
    exc = RateLimitedError("429", retry_after_s=12.5)
    assert policy.delay_for(1, exc) == 12.5
    # Even on a high attempt where exponential would exceed retry-after
    assert policy.delay_for(5, exc) == 12.5


def test_rate_limited_falls_back_when_no_retry_after() -> None:
    policy = RetryPolicy(max_attempts=5, base_delay_s=1, max_delay_s=60, jitter=False)
    exc = RateLimitedError("429", retry_after_s=None)
    assert policy.delay_for(2, exc) == 2.0


def test_attempt_must_be_positive() -> None:
    policy = RetryPolicy()
    with pytest.raises(ValueError):
        policy.delay_for(0)
