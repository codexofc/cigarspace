# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""FastAPI dependency-injection helpers.

Everything that an endpoint needs (settings, DB session, embedder,
authenticated user) is provided via ``Depends(...)`` so the implementations
can be swapped out cleanly in tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, AsyncSession

from domain.entities.api_user import ApiUser
from infrastructure.config.settings import ApiSettings, get_settings as _build_settings
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from presentation.api.security.jwt import JwtError, decode_access_token


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def get_api_settings() -> ApiSettings:
    return _build_settings().api


ApiSettingsDep = Annotated[ApiSettings, Depends(get_api_settings)]


# ---------------------------------------------------------------------------
# Engine / session_factory / UoW — populated by lifespan in main.py
# ---------------------------------------------------------------------------


def get_engine(request: Request) -> AsyncEngine:
    engine: AsyncEngine | None = getattr(request.app.state, "engine", None)
    if engine is None:
        raise RuntimeError("API engine not initialised — lifespan missing?")
    return engine


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise RuntimeError("session_factory not initialised — lifespan missing?")
    return factory


async def get_uow(request: Request) -> AsyncIterator[SqlAlchemyUnitOfWork]:
    """Yield a UoW scoped to one HTTP request.

    Endpoints that only read may simply iterate the data; endpoints that
    mutate must call ``await uow.commit()`` explicitly before returning.
    """
    factory = get_session_factory(request)
    async with SqlAlchemyUnitOfWork(factory) as uow:
        yield uow


UnitOfWorkDep = Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)]


def get_embedder(request: Request):
    """Return the shared sentence-transformer embedder instance."""
    embedder = getattr(request.app.state, "embedder", None)
    if embedder is None:
        raise RuntimeError("Embedder not initialised — lifespan missing?")
    return embedder


def get_redis(request: Request):
    return getattr(request.app.state, "redis", None)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


# The tokenUrl is referenced by Swagger UI's "Authorize" dialog; pointing
# at our own /oauth/token endpoint lets users log in directly from /docs.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/oauth/token",
    auto_error=False,
)


async def get_current_user_optional(
    request: Request,
    settings: ApiSettingsDep,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> ApiUser | None:
    if not token:
        return None
    try:
        claims = decode_access_token(token, settings=settings)
    except JwtError:
        return None
    async for uow in get_uow(request):
        return await uow.api_users.get_by_id(claims.sub)
    return None  # pragma: no cover — generator guaranteed to yield once


async def get_current_user(
    user: Annotated[ApiUser | None, Depends(get_current_user_optional)],
) -> ApiUser:
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(
    user: Annotated[ApiUser, Depends(get_current_user)],
) -> ApiUser:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin scope required",
        )
    return user


CurrentUserDep = Annotated[ApiUser, Depends(get_current_user)]
AdminUserDep = Annotated[ApiUser, Depends(require_admin)]


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pagination:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def pagination(
    settings: ApiSettingsDep,
    page: int = Query(1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(20, ge=1, description="Number of items per page (capped server-side)."),
) -> Pagination:
    page_size = min(page_size, settings.max_page_size)
    offset = (page - 1) * page_size
    if offset > settings.max_offset:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"offset {offset} exceeds the maximum allowed "
                f"({settings.max_offset}); use a finer filter or search."
            ),
        )
    return Pagination(page=page, page_size=page_size)


PaginationDep = Annotated[Pagination, Depends(pagination)]
