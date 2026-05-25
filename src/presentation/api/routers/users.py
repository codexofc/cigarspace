# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""User-facing endpoints (currently just /me)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from presentation.api.dependencies import CurrentUserDep
from presentation.api.hypermedia import make_links
from presentation.api.schemas.user import UserResponse


router = APIRouter(prefix="/me", tags=["Users"])


@router.get(
    "",
    response_model=UserResponse,
    summary="Return the currently authenticated user's profile.",
)
async def read_me(request: Request, user: CurrentUserDep) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        _links=make_links(request, "/api/v1/me"),
    )
