# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""PostgreSQL implementation of the API user + refresh-token repositories."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.api_user import ApiUser, RefreshToken
from infrastructure.persistence.mappers import (
    api_user_to_domain,
    api_user_to_model,
    refresh_token_to_domain,
    refresh_token_to_model,
)
from infrastructure.persistence.models import ApiUserModel, RefreshTokenModel


class PgApiUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> ApiUser | None:
        result = await self._session.execute(select(ApiUserModel).where(ApiUserModel.id == user_id))
        row = result.scalar_one_or_none()
        return api_user_to_domain(row) if row is not None else None

    async def get_by_email(self, email: str) -> ApiUser | None:
        # CITEXT comparison is case-insensitive at the type level — no need
        # to lower() the literal.
        result = await self._session.execute(
            select(ApiUserModel).where(ApiUserModel.email == email)
        )
        row = result.scalar_one_or_none()
        return api_user_to_domain(row) if row is not None else None

    async def add(self, user: ApiUser) -> ApiUser:
        m = api_user_to_model(user)
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return api_user_to_domain(m)

    async def update_last_login(self, user_id: UUID, *, when: datetime) -> None:
        await self._session.execute(
            update(ApiUserModel).where(ApiUserModel.id == user_id).values(last_login_at=when)
        )

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> Sequence[ApiUser]:
        stmt = (
            select(ApiUserModel)
            .order_by(ApiUserModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [api_user_to_domain(m) for m in result.scalars().all()]

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(ApiUserModel))
        return int(result.scalar_one())


class PgRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: RefreshToken) -> RefreshToken:
        m = refresh_token_to_model(token)
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return refresh_token_to_domain(m)

    async def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        )
        row = result.scalar_one_or_none()
        return refresh_token_to_domain(row) if row is not None else None

    async def revoke(self, token_id: UUID, *, when: datetime) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.id == token_id)
            .where(RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=when)
        )

    async def revoke_all_for_user(self, user_id: UUID, *, when: datetime) -> int:
        result = await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id == user_id)
            .where(RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=when)
        )
        return int(result.rowcount or 0)
