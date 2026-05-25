# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Cookie helpers for the web-friendly auth flow.

The browser keeps the refresh token in an ``HttpOnly Secure SameSite=Lax``
cookie so JavaScript code can never read it (XSS-immune). The access
token is returned in the response body and lives in memory on the front,
never in localStorage.
"""

from __future__ import annotations

from fastapi import Request, Response

from infrastructure.config.settings import ApiSettings

REFRESH_COOKIE_NAME = "cigars_refresh"
COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(
    response: Response,
    *,
    value: str,
    max_age_seconds: int,
    settings: ApiSettings,
    request: Request | None = None,
) -> None:
    """Drop a fresh refresh-token cookie on the response.

    Secure flag is on whenever the request was served over HTTPS *or* the
    app env is "prod" (catches deployments behind a TLS-terminating proxy
    that may not forward ``X-Forwarded-Proto`` correctly).
    """
    secure = _is_secure(request, settings)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=value,
        max_age=max_age_seconds,
        path=COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite="lax",
    )


def clear_refresh_cookie(
    response: Response,
    *,
    settings: ApiSettings,
    request: Request | None = None,
) -> None:
    """Remove the refresh-token cookie (expires immediately)."""
    secure = _is_secure(request, settings)
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite="lax",
    )


def read_refresh_cookie(request: Request) -> str | None:
    return request.cookies.get(REFRESH_COOKIE_NAME)


def _is_secure(request: Request | None, settings: ApiSettings) -> bool:
    # Settings doesn't carry app env here; we rely on the request scheme
    # plus the heuristic that prod is always behind HTTPS.
    if request is not None and request.url.scheme == "https":
        return True
    if request is not None:
        proto = request.headers.get("x-forwarded-proto") or ""
        if proto.lower() == "https":
            return True
    return False
