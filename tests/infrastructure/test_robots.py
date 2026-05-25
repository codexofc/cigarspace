# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import httpx
import pytest
import respx

from infrastructure.fetcher.robots import RobotsBlockedError, RobotsPolicy


@respx.mock
async def test_respect_mode_allows_when_allowed() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, content=b"User-agent: *\nDisallow: /private/\n")
    )

    policy = RobotsPolicy(mode="respect", user_agent="cigars-test")
    assert await policy.is_allowed("https://example.com/public/page")


@respx.mock
async def test_respect_mode_blocks_when_disallowed() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, content=b"User-agent: *\nDisallow: /private/\n")
    )

    policy = RobotsPolicy(mode="respect", user_agent="cigars-test")
    assert not await policy.is_allowed("https://example.com/private/secret")

    with pytest.raises(RobotsBlockedError):
        await policy.assert_allowed("https://example.com/private/secret")


@respx.mock
async def test_log_only_mode_allows_despite_disallow() -> None:
    respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, content=b"User-agent: *\nDisallow: /private/\n")
    )

    policy = RobotsPolicy(mode="log_only", user_agent="cigars-test")
    assert await policy.is_allowed("https://example.com/private/secret")


async def test_ignore_mode_never_fetches() -> None:
    # No respx mock at all — if mode=ignore tries to fetch, the test will raise
    policy = RobotsPolicy(mode="ignore", user_agent="cigars-test")
    assert await policy.is_allowed("https://nonexistent.example.com/anything")


@respx.mock
async def test_404_robots_means_full_allow() -> None:
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(404))

    policy = RobotsPolicy(mode="respect", user_agent="cigars-test")
    assert await policy.is_allowed("https://example.com/anything")


@respx.mock
async def test_403_robots_means_disallow_all() -> None:
    respx.get("https://example.com/robots.txt").mock(return_value=httpx.Response(403))

    policy = RobotsPolicy(mode="respect", user_agent="cigars-test")
    assert not await policy.is_allowed("https://example.com/anything")


@respx.mock
async def test_fetch_failure_with_allow_policy() -> None:
    respx.get("https://example.com/robots.txt").mock(side_effect=httpx.ConnectError("down"))

    policy = RobotsPolicy(mode="respect", on_fetch_error="allow", user_agent="cigars-test")
    assert await policy.is_allowed("https://example.com/anything")


@respx.mock
async def test_fetch_failure_with_deny_policy() -> None:
    respx.get("https://example.com/robots.txt").mock(side_effect=httpx.ConnectError("down"))

    policy = RobotsPolicy(mode="respect", on_fetch_error="deny", user_agent="cigars-test")
    assert not await policy.is_allowed("https://example.com/anything")


@respx.mock
async def test_cache_avoids_refetch() -> None:
    route = respx.get("https://example.com/robots.txt").mock(
        return_value=httpx.Response(200, content=b"User-agent: *\nAllow: /\n")
    )

    policy = RobotsPolicy(mode="respect", user_agent="cigars-test", cache_ttl_s=3600)
    await policy.is_allowed("https://example.com/a")
    await policy.is_allowed("https://example.com/b")
    await policy.is_allowed("https://example.com/c")

    assert route.call_count == 1


@respx.mock
async def test_per_host_override() -> None:
    respx.get("https://strict.example.com/robots.txt").mock(
        return_value=httpx.Response(200, content=b"User-agent: *\nDisallow: /\n")
    )

    policy = RobotsPolicy(
        mode="respect",
        user_agent="cigars-test",
        overrides={"strict.example.com": "ignore"},
    )
    # Despite disallow-all, override says 'ignore' → allow
    assert await policy.is_allowed("https://strict.example.com/anything")
