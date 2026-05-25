# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""OAuth flow integration tests."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_password_grant_returns_tokens(api_client, seeded_universe) -> None:
    r = await api_client.post(
        "/api/v1/oauth/token",
        json={
            "grant_type": "password",
            "email": seeded_universe["admin_email"],
            "password": seeded_universe["admin_password"],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "Bearer"
    assert "access_token" in body and "refresh_token" in body
    assert body["expires_in"] >= 60
    assert "admin" in body["scope"]


async def test_password_grant_rejects_wrong_password(api_client, seeded_universe) -> None:
    r = await api_client.post(
        "/api/v1/oauth/token",
        json={
            "grant_type": "password",
            "email": seeded_universe["admin_email"],
            "password": "wrong-pass",
        },
    )
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


async def test_refresh_token_rotates(api_client, seeded_universe) -> None:
    r = await api_client.post(
        "/api/v1/oauth/token",
        json={
            "grant_type": "password",
            "email": seeded_universe["reader_email"],
            "password": seeded_universe["reader_password"],
        },
    )
    first = r.json()
    refreshed = await api_client.post(
        "/api/v1/oauth/token",
        json={
            "grant_type": "refresh_token",
            "refresh_token": first["refresh_token"],
        },
    )
    assert refreshed.status_code == 200, refreshed.text
    second = refreshed.json()
    assert second["refresh_token"] != first["refresh_token"]


async def test_refresh_token_reuse_cascade_revoke(api_client, seeded_universe) -> None:
    r = await api_client.post(
        "/api/v1/oauth/token",
        json={
            "grant_type": "password",
            "email": seeded_universe["reader_email"],
            "password": seeded_universe["reader_password"],
        },
    )
    first = r.json()
    # First refresh consumes the token (revokes it, returns a new one).
    await api_client.post(
        "/api/v1/oauth/token",
        json={"grant_type": "refresh_token", "refresh_token": first["refresh_token"]},
    )
    # Replaying the revoked token must fail with 401.
    replay = await api_client.post(
        "/api/v1/oauth/token",
        json={"grant_type": "refresh_token", "refresh_token": first["refresh_token"]},
    )
    assert replay.status_code == 401


async def test_revoke_endpoint(api_client, seeded_universe) -> None:
    r = await api_client.post(
        "/api/v1/oauth/token",
        json={
            "grant_type": "password",
            "email": seeded_universe["reader_email"],
            "password": seeded_universe["reader_password"],
        },
    )
    body = r.json()
    rev = await api_client.post(
        "/api/v1/oauth/revoke",
        json={"refresh_token": body["refresh_token"]},
    )
    assert rev.status_code == 200
    assert rev.json()["revoked"] is True

    # Subsequent refresh attempts on the revoked token must fail.
    again = await api_client.post(
        "/api/v1/oauth/token",
        json={"grant_type": "refresh_token", "refresh_token": body["refresh_token"]},
    )
    assert again.status_code == 401


async def test_me_endpoint(api_client, seeded_universe, reader_token) -> None:
    r = await api_client.get("/api/v1/me", headers={"Authorization": f"Bearer {reader_token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == seeded_universe["reader_email"]
    assert body["is_admin"] is False
    assert body["_links"]["self"].endswith("/api/v1/me")


async def test_me_requires_auth(api_client) -> None:
    r = await api_client.get("/api/v1/me")
    assert r.status_code == 401
