# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import httpx
import pytest
import respx

from infrastructure.config.settings import PisteSettings
from infrastructure.customs.piste_oauth import PisteOAuthClient


def _settings() -> PisteSettings:
    return PisteSettings(
        client_id="fake-id",
        client_secret="fake-secret",
        oauth_url="https://oauth.test/api/oauth/token",
        api_base_url="https://api.test/dila",
        scope="openid",
    )


def test_missing_credentials_raises() -> None:
    with pytest.raises(RuntimeError) as ei:
        PisteOAuthClient(PisteSettings(client_id="", client_secret=""))
    assert "PISTE credentials" in str(ei.value)


@respx.mock
async def test_first_call_fetches_token() -> None:
    respx.post("https://oauth.test/api/oauth/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "tok-aaa",
                "expires_in": 1800,
                "token_type": "Bearer",
            },
        )
    )
    client = PisteOAuthClient(_settings())
    headers = await client.auth_headers()
    assert headers == {"Authorization": "Bearer tok-aaa"}


@respx.mock
async def test_token_is_cached_until_expiry() -> None:
    route = respx.post("https://oauth.test/api/oauth/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "tok-bbb", "expires_in": 1800},
        )
    )
    client = PisteOAuthClient(_settings())
    h1 = await client.auth_headers()
    h2 = await client.auth_headers()
    h3 = await client.auth_headers()
    assert h1 == h2 == h3
    assert route.call_count == 1


@respx.mock
async def test_invalidate_forces_refresh() -> None:
    route = respx.post("https://oauth.test/api/oauth/token").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "tok-1", "expires_in": 1800}),
            httpx.Response(200, json={"access_token": "tok-2", "expires_in": 1800}),
        ]
    )
    client = PisteOAuthClient(_settings())
    h1 = await client.auth_headers()
    client.invalidate()
    h2 = await client.auth_headers()
    assert h1["Authorization"] == "Bearer tok-1"
    assert h2["Authorization"] == "Bearer tok-2"
    assert route.call_count == 2
