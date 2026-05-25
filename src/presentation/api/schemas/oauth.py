# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""OAuth2 request / response models (RFC 6749 password + refresh_token)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OAuthTokenRequest(BaseModel):
    """Body of ``POST /api/v1/oauth/token``.

    The two grant types we support are ``password`` and ``refresh_token``.
    Fields required differ per grant — runtime validation enforces it.
    """

    model_config = ConfigDict(extra="forbid")

    grant_type: Literal["password", "refresh_token"] = Field(
        description="OAuth2 grant type (RFC 6749 §4)."
    )
    email: EmailStr | None = Field(
        default=None,
        description="Required when grant_type=password.",
        examples=["admin@cigars.local"],
    )
    password: str | None = Field(
        default=None,
        description="Required when grant_type=password.",
        examples=["s3cret"],
    )
    refresh_token: str | None = Field(
        default=None,
        description="Required when grant_type=refresh_token.",
    )
    scope: str | None = Field(
        default=None,
        description="Space-separated scope subset; ignored if broader than user grant.",
    )


class TokenResponse(BaseModel):
    """RFC 6749 §5.1 token response."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int = Field(
        description="Lifetime of the access token in seconds.",
        examples=[900],
    )
    refresh_token: str
    scope: str = Field(
        description="Space-separated list of granted scopes.",
        examples=["read admin"],
    )


class RevokeRequest(BaseModel):
    """Body of ``POST /api/v1/oauth/revoke`` (RFC 7009)."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(description="The refresh token to revoke.")
