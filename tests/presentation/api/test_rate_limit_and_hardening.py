# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Rate-limit + prod hardening tests."""

from __future__ import annotations

import pytest

from presentation.api.main import _validate_prod_hardening

pytestmark = pytest.mark.asyncio


async def test_rate_limit_triggers_429_on_oauth_token(api_client, seeded_universe):
    """The /oauth/token endpoint is capped at 10 req/min/IP."""

    bad_credentials = {
        "grant_type": "password",
        "email": seeded_universe["admin_email"],
        "password": "wrong",
    }
    last_status = 401
    saw_429 = False
    # Fire 15 requests; we expect 429 to kick in somewhere between #11 and #15.
    for _ in range(15):
        r = await api_client.post("/api/v1/oauth/token", json=bad_credentials)
        last_status = r.status_code
        if last_status == 429:
            saw_429 = True
            assert r.headers.get("retry-after") is not None
            body = r.json()
            assert body["type"] == "errors/too-many-requests"
            assert body["title"] == "Too Many Requests"
            break
    assert saw_429, f"expected 429 after 15 attempts, last={last_status}"


# --- Prod hardening (pure unit, no app boot) -------------------------------


class _ApiCfg:
    def __init__(self, **kw):
        defaults = dict(
            cors_origins=["https://app.cigars.io"],
            jwt_secret="a" * 40,
        )
        defaults.update(kw)
        self.cors_origins = defaults["cors_origins"]
        self.jwt_secret = defaults["jwt_secret"]


def test_prod_hardening_passes_with_strong_settings():
    _validate_prod_hardening("prod", _ApiCfg())  # must not raise


def test_prod_hardening_rejects_wildcard_cors():
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        _validate_prod_hardening("prod", _ApiCfg(cors_origins=["*"]))


def test_prod_hardening_rejects_default_jwt_secret():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        _validate_prod_hardening("prod", _ApiCfg(jwt_secret="change-me-in-production"))


def test_prod_hardening_rejects_short_jwt_secret():
    with pytest.raises(RuntimeError, match="32 bytes"):
        _validate_prod_hardening("prod", _ApiCfg(jwt_secret="too-short"))


def test_dev_env_is_permissive():
    """Identical weak settings are accepted in dev/test envs."""
    _validate_prod_hardening(
        "dev",
        _ApiCfg(cors_origins=["*"], jwt_secret="change-me"),
    )
    _validate_prod_hardening(
        "test",
        _ApiCfg(cors_origins=["*"], jwt_secret="change-me"),
    )
