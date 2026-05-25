# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""JWT (access) + opaque refresh-token helpers.

Two distinct token formats:
- **Access token**: short-lived (default 15 min) JWT signed HS256.
  Claims: ``sub`` (user UUID), ``exp``, ``iat``, ``scope`` (list of
  strings: ``"read"``, optionally ``"admin"``).
- **Refresh token**: opaque, 32 random bytes encoded base64url, never
  parsed; stored in DB as SHA-256 hex.

Both kinds carry a ``jti`` so a stolen access token can be tracked back
to a session if needed.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt

from infrastructure.config.settings import ApiSettings


_REFRESH_TOKEN_BYTES = 32


@dataclass(frozen=True)
class AccessTokenClaims:
    """Validated access-token payload."""

    sub: UUID
    scope: tuple[str, ...]
    jti: UUID
    iat: datetime
    exp: datetime


class JwtError(Exception):
    """Raised for any token decode / signature / expiry failure."""


def encode_access_token(
    *,
    user_id: UUID,
    scopes: list[str],
    settings: ApiSettings,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    """Mint an access token and return ``(token, expires_at)``."""
    now = now or datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(seconds=settings.access_token_expire_seconds)
    payload = {
        "sub": str(user_id),
        "scope": scopes,
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_access_token(token: str, *, settings: ApiSettings) -> AccessTokenClaims:
    """Return claims if the token is valid, raise :class:`JwtError` otherwise."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "exp", "iat", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise JwtError(str(exc)) from exc
    try:
        return AccessTokenClaims(
            sub=UUID(payload["sub"]),
            scope=tuple(payload.get("scope") or ()),
            jti=UUID(payload["jti"]),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise JwtError(f"malformed claims: {exc}") from exc


def generate_refresh_token() -> tuple[str, str]:
    """Return ``(opaque_plain, sha256_hex)``.

    ``opaque_plain`` is sent to the client once at issuance and never
    persisted server-side; ``sha256_hex`` is what we store.
    """
    plain = secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)
    return plain, hash_refresh_token(plain)


def hash_refresh_token(plain: str) -> str:
    """Constant-time-safe SHA-256 hex digest of an opaque refresh secret."""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def refresh_token_expires_at(settings: ApiSettings, *, now: datetime | None = None) -> datetime:
    now = now or datetime.now(tz=timezone.utc)
    return now + timedelta(seconds=settings.refresh_token_expire_seconds)
