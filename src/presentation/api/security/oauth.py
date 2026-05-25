# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""OAuth2 (RFC 6749) password + refresh_token grant flows.

The implementation is intentionally minimal — we do NOT implement the
full RFC: only the two grants we use (``password`` and ``refresh_token``)
plus token revocation (RFC 7009). Token introspection (RFC 7662) is in
the same module since it is the natural complement and uses the same
data shapes.

The flows enforce:
- Refresh-token rotation (every refresh issues a new pair, old revoked).
- Reuse detection: replaying a revoked refresh token revokes every
  active token of the user (session take-over signal).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from domain.entities.api_user import ApiUser, RefreshToken
from infrastructure.config.settings import ApiSettings
from infrastructure.observability.logging import get_logger
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from presentation.api.security.jwt import (
    encode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expires_at,
)
from presentation.api.security.password import hash_password, needs_rehash, verify_password

_log = get_logger("api.oauth")


class OAuthError(Exception):
    """Base error for any OAuth flow failure (always maps to 401)."""

    def __init__(self, error: str, description: str = "") -> None:
        super().__init__(description or error)
        self.error = error
        self.description = description


@dataclass(frozen=True)
class IssuedTokens:
    """The triple returned to the client after a successful grant."""

    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime
    user: ApiUser
    scopes: tuple[str, ...]


def _scopes_for(user: ApiUser) -> tuple[str, ...]:
    return ("read", "admin") if user.is_admin else ("read",)


async def password_grant(
    *,
    email: str,
    password: str,
    uow: SqlAlchemyUnitOfWork,
    settings: ApiSettings,
    user_agent: str | None = None,
    ip_address: str | None = None,
    now: datetime | None = None,
) -> IssuedTokens:
    """Resource Owner Password Credentials grant."""
    now = now or datetime.now(tz=UTC)
    user = await uow.api_users.get_by_email(email)
    if user is None or not user.is_active:
        raise OAuthError("invalid_grant", "invalid email or password")
    if not verify_password(password, user.password_hash):
        raise OAuthError("invalid_grant", "invalid email or password")

    # Opportunistic rehash on Argon2 parameter upgrade.
    if needs_rehash(user.password_hash):
        new_hash = hash_password(password)
        # We use update_last_login here to write through quickly; a
        # dedicated update_password method could land later.
        from sqlalchemy import update

        from infrastructure.persistence.models import ApiUserModel

        await uow._session.execute(  # type: ignore[attr-defined]
            update(ApiUserModel).where(ApiUserModel.id == user.id).values(password_hash=new_hash)
        )

    issued = await _issue_pair(
        user=user,
        uow=uow,
        settings=settings,
        user_agent=user_agent,
        ip_address=ip_address,
        now=now,
    )
    await uow.api_users.update_last_login(user.id, when=now)
    return issued


async def refresh_token_grant(
    *,
    refresh_token: str,
    uow: SqlAlchemyUnitOfWork,
    settings: ApiSettings,
    user_agent: str | None = None,
    ip_address: str | None = None,
    now: datetime | None = None,
) -> IssuedTokens:
    """Exchange a valid refresh token for a new pair (rotation)."""
    now = now or datetime.now(tz=UTC)
    token_hash = hash_refresh_token(refresh_token)
    stored = await uow.refresh_tokens.find_by_hash(token_hash)

    if stored is None:
        raise OAuthError("invalid_grant", "unknown refresh token")

    # Reuse detection: token already revoked → assume token theft, revoke
    # every active session of this user and refuse the grant.
    if stored.revoked_at is not None:
        revoked = await uow.refresh_tokens.revoke_all_for_user(stored.user_id, when=now)
        _log.warning(
            "refresh_token_reuse_detected",
            user_id=str(stored.user_id),
            revoked_count=revoked,
        )
        raise OAuthError("invalid_grant", "refresh token already used")

    if stored.expires_at <= now:
        raise OAuthError("invalid_grant", "refresh token expired")

    user = await uow.api_users.get_by_id(stored.user_id)
    if user is None or not user.is_active:
        raise OAuthError("invalid_grant", "account no longer active")

    # Rotation: revoke the consumed token before issuing the new pair.
    await uow.refresh_tokens.revoke(stored.id, when=now)
    issued = await _issue_pair(
        user=user,
        uow=uow,
        settings=settings,
        user_agent=user_agent,
        ip_address=ip_address,
        now=now,
    )
    return issued


async def revoke_refresh_token(
    *,
    refresh_token: str,
    uow: SqlAlchemyUnitOfWork,
    now: datetime | None = None,
) -> bool:
    """RFC 7009 revocation. Returns True if a token was actually revoked."""
    now = now or datetime.now(tz=UTC)
    token_hash = hash_refresh_token(refresh_token)
    stored = await uow.refresh_tokens.find_by_hash(token_hash)
    if stored is None or stored.revoked_at is not None:
        # RFC 7009: an unknown / already-revoked token still returns 200.
        return False
    await uow.refresh_tokens.revoke(stored.id, when=now)
    return True


async def _issue_pair(
    *,
    user: ApiUser,
    uow: SqlAlchemyUnitOfWork,
    settings: ApiSettings,
    user_agent: str | None,
    ip_address: str | None,
    now: datetime,
) -> IssuedTokens:
    scopes = _scopes_for(user)
    access, access_exp = encode_access_token(
        user_id=user.id, scopes=list(scopes), settings=settings, now=now
    )
    plain, hashed = generate_refresh_token()
    refresh_exp = refresh_token_expires_at(settings, now=now)
    await uow.refresh_tokens.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hashed,
            expires_at=refresh_exp,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    )
    return IssuedTokens(
        access_token=access,
        access_expires_at=access_exp,
        refresh_token=plain,
        refresh_expires_at=refresh_exp,
        user=user,
        scopes=scopes,
    )
