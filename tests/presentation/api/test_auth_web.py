# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Tests for the cookie-based web auth endpoints."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


_LOGIN = "/api/v1/auth/login"
_REFRESH = "/api/v1/auth/refresh"
_LOGOUT = "/api/v1/auth/logout"


async def test_login_sets_refresh_cookie_and_returns_access(api_client, seeded_universe) -> None:
    r = await api_client.post(
        _LOGIN,
        json={
            "email": seeded_universe["reader_email"],
            "password": seeded_universe["reader_password"],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "Bearer"
    assert "access_token" in body
    # refresh_token must NOT leak in the JSON body
    assert "refresh_token" not in body
    # but the cookie must be set, HttpOnly
    set_cookie = r.headers.get("set-cookie", "")
    assert "cigars_refresh=" in set_cookie
    assert "HttpOnly" in set_cookie or "httponly" in set_cookie.lower()


async def test_login_bad_password_returns_401(api_client, seeded_universe) -> None:
    r = await api_client.post(
        _LOGIN,
        json={"email": seeded_universe["reader_email"], "password": "nope"},
    )
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


async def test_refresh_uses_cookie(api_client, seeded_universe) -> None:
    # First, login to plant the cookie.
    await api_client.post(
        _LOGIN,
        json={
            "email": seeded_universe["admin_email"],
            "password": seeded_universe["admin_password"],
        },
    )
    # httpx AsyncClient carries cookies across calls by default.
    r = await api_client.post(_REFRESH)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body
    # Cookie is rotated.
    assert "cigars_refresh=" in r.headers.get("set-cookie", "")


async def test_refresh_without_cookie_returns_401(api_client) -> None:
    # Use a fresh client cookie jar.
    api_client.cookies.clear()
    r = await api_client.post(_REFRESH)
    assert r.status_code == 401
    assert "missing refresh cookie" in r.json()["detail"].lower()


async def test_logout_revokes_and_clears_cookie(api_client, seeded_universe) -> None:
    r = await api_client.post(
        _LOGIN,
        json={
            "email": seeded_universe["admin_email"],
            "password": seeded_universe["admin_password"],
        },
    )
    access = r.json()["access_token"]
    r2 = await api_client.post(_LOGOUT, headers={"Authorization": f"Bearer {access}"})
    assert r2.status_code == 204
    # The Set-Cookie header should expire the cookie.
    set_cookie = r2.headers.get("set-cookie", "")
    assert "cigars_refresh=" in set_cookie
    # Trying to refresh now must fail.
    r3 = await api_client.post(_REFRESH)
    assert r3.status_code == 401


async def test_logout_requires_authenticated_user(api_client) -> None:
    api_client.cookies.clear()
    r = await api_client.post(_LOGOUT)
    assert r.status_code == 401
