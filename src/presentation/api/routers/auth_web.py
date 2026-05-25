# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Web-friendly auth endpoints (cookie-based refresh).

Mirrors the OAuth2 flows under /oauth/* but persists the refresh token
in an HttpOnly cookie so browser clients don't have to handle it in JS.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from presentation.api.dependencies import (
    ApiSettingsDep,
    CurrentUserDep,
    UnitOfWorkDep,
)
from presentation.api.errors import ErrorResponse
from presentation.api.rate_limit import limiter
from presentation.api.security.cookies import (
    clear_refresh_cookie,
    read_refresh_cookie,
    set_refresh_cookie,
)
from presentation.api.security.oauth import (
    OAuthError,
    password_grant,
    refresh_token_grant,
    revoke_refresh_token,
)


router = APIRouter(prefix="/auth", tags=["Auth (Web)"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class WebAccessResponse(BaseModel):
    """Body returned by /auth/login and /auth/refresh.

    The refresh token is **not** in the body — it lives in the HttpOnly
    ``cigars_refresh`` cookie which the browser forwards automatically.
    """

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int = Field(description="Lifetime of the access token in seconds.")
    scope: str = Field(description="Space-separated list of granted scopes.")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


_LOGIN_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Bad email/password."},
    422: {"model": ErrorResponse, "description": "Validation error."},
    429: {"model": ErrorResponse, "description": "Too many login attempts."},
}


@router.post(
    "/login",
    response_model=WebAccessResponse,
    summary="Browser login — sets the refresh cookie, returns access in body.",
    responses=_LOGIN_RESPONSES,
)
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    uow: UnitOfWorkDep,
    settings: ApiSettingsDep,
) -> WebAccessResponse:
    try:
        issued = await password_grant(
            email=body.email,
            password=body.password,
            uow=uow,
            settings=settings,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except OAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.description or exc.error,
            headers={"WWW-Authenticate": f'Bearer error="{exc.error}"'},
        )
    await uow.commit()
    set_refresh_cookie(
        response,
        value=issued.refresh_token,
        max_age_seconds=settings.refresh_token_expire_seconds,
        settings=settings,
        request=request,
    )
    return WebAccessResponse(
        access_token=issued.access_token,
        expires_in=settings.access_token_expire_seconds,
        scope=" ".join(issued.scopes),
    )


@router.post(
    "/refresh",
    response_model=WebAccessResponse,
    summary="Rotate the refresh cookie + return a fresh access token.",
    responses={
        401: {"model": ErrorResponse, "description": "Missing or expired cookie."},
        429: {"model": ErrorResponse, "description": "Too many refreshes."},
    },
)
@limiter.limit("60/minute")
async def refresh(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    settings: ApiSettingsDep,
) -> WebAccessResponse:
    cookie = read_refresh_cookie(request)
    if not cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing refresh cookie",
        )
    try:
        issued = await refresh_token_grant(
            refresh_token=cookie,
            uow=uow,
            settings=settings,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except OAuthError as exc:
        # Clear the cookie so the browser doesn't keep retrying a dead token.
        clear_refresh_cookie(response, settings=settings, request=request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.description or exc.error,
        )
    await uow.commit()
    set_refresh_cookie(
        response,
        value=issued.refresh_token,
        max_age_seconds=settings.refresh_token_expire_seconds,
        settings=settings,
        request=request,
    )
    return WebAccessResponse(
        access_token=issued.access_token,
        expires_in=settings.access_token_expire_seconds,
        scope=" ".join(issued.scopes),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current refresh token + clear the cookie.",
)
async def logout(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    settings: ApiSettingsDep,
    user: CurrentUserDep,  # ensures a valid access token is presented
) -> None:
    cookie = read_refresh_cookie(request)
    if cookie:
        await revoke_refresh_token(refresh_token=cookie, uow=uow)
        await uow.commit()
    # We mutate the injected response (which FastAPI returns for us) so the
    # cookie-clearing Set-Cookie header survives next to the 204.
    clear_refresh_cookie(response, settings=settings, request=request)
    response.status_code = status.HTTP_204_NO_CONTENT
    return None
