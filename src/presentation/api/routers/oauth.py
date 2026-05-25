# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""OAuth2 endpoints: token issuance, refresh, revocation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from presentation.api.dependencies import ApiSettingsDep, UnitOfWorkDep
from presentation.api.errors import ErrorResponse
from presentation.api.rate_limit import limiter
from presentation.api.schemas.oauth import (
    OAuthTokenRequest,
    RevokeRequest,
    TokenResponse,
)
from presentation.api.security.oauth import (
    OAuthError,
    password_grant,
    refresh_token_grant,
    revoke_refresh_token,
)


router = APIRouter(prefix="/oauth", tags=["OAuth"])


_TOKEN_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Malformed grant request."},
    401: {"model": ErrorResponse, "description": "Invalid credentials or token."},
    422: {"model": ErrorResponse, "description": "Validation error."},
}


def _client_metadata(request: Request) -> tuple[str | None, str | None]:
    ua = request.headers.get("user-agent")
    client = request.client.host if request.client else None
    return ua, client


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Issue access + refresh tokens (RFC 6749 §4.3 / §6).",
    description=(
        "Exchanges either:\n"
        "* **password grant** — `email` + `password` for a brand-new pair, or\n"
        "* **refresh_token grant** — a non-revoked refresh token for a rotated pair.\n"
        "\n"
        "Refresh tokens rotate on every successful refresh: replaying a "
        "revoked refresh token triggers a cascade revocation of every active "
        "session of the user.\n"
        "\n"
        "**Rate limit**: 10 req/min/IP. Breach returns HTTP 429 + `Retry-After`."
    ),
    responses={
        **_TOKEN_ERROR_RESPONSES,
        200: {"model": TokenResponse},
        429: {"model": ErrorResponse, "description": "Too many login attempts."},
    },
)
@limiter.limit("10/minute")
async def issue_tokens(
    request: Request,
    response: Response,
    body: OAuthTokenRequest,
    uow: UnitOfWorkDep,
    settings: ApiSettingsDep,
) -> TokenResponse:
    user_agent, ip = _client_metadata(request)
    try:
        if body.grant_type == "password":
            if not body.email or not body.password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="email and password are required for grant_type=password",
                )
            issued = await password_grant(
                email=body.email,
                password=body.password,
                uow=uow,
                settings=settings,
                user_agent=user_agent,
                ip_address=ip,
            )
        elif body.grant_type == "refresh_token":
            if not body.refresh_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="refresh_token is required for grant_type=refresh_token",
                )
            issued = await refresh_token_grant(
                refresh_token=body.refresh_token,
                uow=uow,
                settings=settings,
                user_agent=user_agent,
                ip_address=ip,
            )
        else:  # pragma: no cover — Pydantic literal blocks anything else
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="unsupported grant_type",
            )
    except OAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.description or exc.error,
            headers={"WWW-Authenticate": f'Bearer error="{exc.error}"'},
        )
    await uow.commit()
    return TokenResponse(
        access_token=issued.access_token,
        expires_in=settings.access_token_expire_seconds,
        refresh_token=issued.refresh_token,
        scope=" ".join(issued.scopes),
    )


@router.post(
    "/revoke",
    status_code=status.HTTP_200_OK,
    summary="Revoke a refresh token (RFC 7009).",
    description=(
        "Revokes the supplied refresh token. Per RFC 7009, the response is "
        "200 even when the token is unknown or already revoked so callers "
        "cannot probe token validity.\n"
        "\n"
        "**Rate limit**: 30 req/min/IP."
    ),
)
@limiter.limit("30/minute")
async def revoke_token(
    request: Request,
    response: Response,
    body: RevokeRequest,
    uow: UnitOfWorkDep,
) -> dict[str, bool]:
    revoked = await revoke_refresh_token(refresh_token=body.refresh_token, uow=uow)
    await uow.commit()
    return {"revoked": revoked}
