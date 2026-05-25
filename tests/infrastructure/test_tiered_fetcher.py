# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from application.ports.fetcher import (
    FetchRequest,
    FetchResponse,
    ForbiddenError,
    NetworkError,
)
from infrastructure.fetcher.soft_ban import SoftBanDetector
from infrastructure.fetcher.tiered import TieredFetcher


class _Fetcher:
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


def _ok(url: str = "https://x.example.com/", tag: str = "ok", body: bytes = b"ok") -> FetchResponse:
    return FetchResponse(
        url=url,
        status_code=200,
        headers={"x-tag": tag, "content-type": "text/html"},
        body=body,
        elapsed_s=0.01,
        fetched_at=datetime.now(tz=UTC),
    )


def test_invalid_args_rejected() -> None:
    with pytest.raises(ValueError):
        TieredFetcher(tiers=[])
    with pytest.raises(ValueError):
        TieredFetcher(
            tiers=[("l0", _Fetcher([])), ("l1", _Fetcher([]))],
            escalate_after_403=0,
        )


async def test_first_call_uses_l0_on_success() -> None:
    l0 = _Fetcher([_ok(tag="from-l0")])
    l1 = _Fetcher([])
    tf = TieredFetcher.with_default_pipeline(l0=l0, l1=l1)

    resp = await tf.fetch(FetchRequest(url="https://x.example.com/"))

    assert resp.headers["x-tag"] == "from-l0"
    assert len(l0.calls) == 1
    assert len(l1.calls) == 0
    assert tf.tier_for("https://x.example.com/") == "l0"


async def test_403_at_l0_falls_through_to_l1() -> None:
    l0 = _Fetcher([ForbiddenError("blocked", url="https://x.example.com/")])
    l1 = _Fetcher([_ok(tag="from-l1")])
    tf = TieredFetcher.with_default_pipeline(l0=l0, l1=l1, escalate_after_403=2)

    resp = await tf.fetch(FetchRequest(url="https://x.example.com/"))

    assert resp.headers["x-tag"] == "from-l1"
    assert len(l0.calls) == 1
    assert len(l1.calls) == 1


async def test_escalation_after_threshold_pins_to_l1() -> None:
    l0 = _Fetcher(
        [
            ForbiddenError("blocked1", url="https://x.example.com/"),
            _ok(tag="from-l0"),  # would be served if not pinned
        ]
    )
    l1 = _Fetcher([_ok(tag="from-l1"), _ok(tag="from-l1")])
    tf = TieredFetcher.with_default_pipeline(l0=l0, l1=l1, escalate_after_403=1)

    # First call: L0 fails → L1 succeeds, domain pinned to L1
    await tf.fetch(FetchRequest(url="https://x.example.com/"))
    assert tf.tier_for("https://x.example.com/") == "l1"

    # Second call: must bypass L0 entirely
    resp = await tf.fetch(FetchRequest(url="https://x.example.com/"))
    assert resp.headers["x-tag"] == "from-l1"
    assert len(l0.calls) == 1  # unchanged
    assert len(l1.calls) == 2


async def test_escalation_is_per_domain() -> None:
    l0 = _Fetcher(
        [
            ForbiddenError("blocked", url="https://a.example.com/"),
            _ok(tag="from-l0"),
        ]
    )
    l1 = _Fetcher([_ok(tag="from-l1")])
    tf = TieredFetcher.with_default_pipeline(l0=l0, l1=l1, escalate_after_403=1)

    await tf.fetch(FetchRequest(url="https://a.example.com/"))
    assert tf.tier_for("https://a.example.com/") == "l1"

    resp = await tf.fetch(FetchRequest(url="https://b.example.com/"))
    assert resp.headers["x-tag"] == "from-l0"
    assert tf.tier_for("https://b.example.com/") == "l0"


async def test_non_forbidden_error_propagates_immediately() -> None:
    l0 = _Fetcher([NetworkError("dns", url="https://x.example.com/")])
    l1 = _Fetcher([])
    tf = TieredFetcher.with_default_pipeline(l0=l0, l1=l1)

    with pytest.raises(NetworkError):
        await tf.fetch(FetchRequest(url="https://x.example.com/"))

    assert tf.tier_for("https://x.example.com/") == "l0"
    assert len(l1.calls) == 0


async def test_three_tiers_cascade() -> None:
    l0 = _Fetcher([ForbiddenError("blocked", url="https://x.example.com/")])
    l1 = _Fetcher([ForbiddenError("still blocked", url="https://x.example.com/")])
    l2 = _Fetcher([_ok(tag="from-l2")])
    tf = TieredFetcher.with_default_pipeline(l0=l0, l1=l1, l2=l2)

    resp = await tf.fetch(FetchRequest(url="https://x.example.com/"))

    assert resp.headers["x-tag"] == "from-l2"
    assert len(l0.calls) == 1
    assert len(l1.calls) == 1
    assert len(l2.calls) == 1


async def test_soft_ban_triggers_escalation() -> None:
    # L0 returns 200 with a Cloudflare challenge in the body
    cf_body = b"<html><body><div class='cf-turnstile'>Just a moment...</div></body></html>"
    l0 = _Fetcher([_ok(tag="cf-page", body=cf_body)])
    l1 = _Fetcher([_ok(tag="from-l1", body=b"<html><body>Real page</body></html>")])
    tf = TieredFetcher.with_default_pipeline(l0=l0, l1=l1, soft_ban_detector=SoftBanDetector())

    resp = await tf.fetch(FetchRequest(url="https://x.example.com/"))

    assert resp.headers["x-tag"] == "from-l1"
    assert len(l0.calls) == 1
    assert len(l1.calls) == 1


async def test_all_tiers_exhausted_raises() -> None:
    l0 = _Fetcher([ForbiddenError("blocked", url="https://x.example.com/")])
    l1 = _Fetcher([ForbiddenError("blocked", url="https://x.example.com/")])
    tf = TieredFetcher.with_default_pipeline(l0=l0, l1=l1)

    with pytest.raises(ForbiddenError):
        await tf.fetch(FetchRequest(url="https://x.example.com/"))
