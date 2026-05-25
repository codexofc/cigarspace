# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""OAuth2 client for the PISTE platform (gateway to the DILA Légifrance API).

PISTE issues short-lived bearer tokens via client_credentials flow:

  POST https://oauth.piste.gouv.fr/api/oauth/token
       client_id, client_secret, grant_type=client_credentials, scope=openid
  → { "access_token": "...", "expires_in": 1800, "token_type": "Bearer" }

We cache the token in-memory until shortly before expiry (60 s safety
margin) to avoid hammering the OAuth endpoint.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from infrastructure.config import PisteSettings


@dataclass
class _CachedToken:
    access_token: str
    expires_at_monotonic: float


class PisteOAuthClient:
    """Thread-safe-ish OAuth2 client_credentials helper.

    `auth_headers()` is the only method callers need — it returns a dict
    suitable for splatting into httpx headers (or `FetchRequest.headers`)
    with a valid bearer token.
    """

    def __init__(self, settings: PisteSettings, *, safety_margin_s: float = 60.0) -> None:
        if not settings.client_id or not settings.client_secret:
            raise RuntimeError(
                "PISTE credentials not configured — set PISTE_CLIENT_ID and "
                "PISTE_CLIENT_SECRET in .env"
            )
        self._settings = settings
        self._margin = safety_margin_s
        self._cache: _CachedToken | None = None

    async def auth_headers(self) -> dict[str, str]:
        token = await self._get_token()
        return {"Authorization": f"Bearer {token}"}

    async def _get_token(self) -> str:
        now = time.monotonic()
        if self._cache and self._cache.expires_at_monotonic > now:
            return self._cache.access_token
        return await self._refresh()

    async def _refresh(self) -> str:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                self._settings.oauth_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._settings.client_id,
                    "client_secret": self._settings.client_secret,
                    "scope": self._settings.scope,
                },
            )
        response.raise_for_status()
        payload = response.json()
        access_token = payload["access_token"]
        expires_in = float(payload.get("expires_in", 1800))
        self._cache = _CachedToken(
            access_token=access_token,
            expires_at_monotonic=time.monotonic() + expires_in - self._margin,
        )
        return access_token

    def invalidate(self) -> None:
        """Force a fresh token on the next request (e.g. after a 401)."""
        self._cache = None
