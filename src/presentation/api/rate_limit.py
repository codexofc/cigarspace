# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Rate-limiting via slowapi.

The ``limiter`` instance is a module-level singleton so route handlers can
decorate themselves with ``@limiter.limit("5/minute")``. The storage URI is
read from ``Settings.redis.dsn`` at import time; fall back to in-memory if
Redis is unreachable when the API boots so dev / tests still work.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from infrastructure.config import get_settings
from infrastructure.observability.logging import get_logger
from presentation.api.errors import _build  # re-use the RFC 7807 builder
from presentation.api.security.jwt import JwtError, decode_access_token

_log = get_logger("api.rate_limit")


def _client_ip(request: Request) -> str:
    """Real client IP, taking ``X-Forwarded-For`` into account when proxied."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def _user_or_ip_key(request: Request) -> str:
    """Bucket by authenticated user when a valid bearer is present, by IP
    otherwise. This way an authenticated client gets its own quota and is
    not throttled by traffic from its NAT/load-balancer peers."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(None, 1)[1]
        settings_root = getattr(request.app.state, "settings", None)
        api_settings = getattr(settings_root, "api", None) if settings_root else None
        if api_settings is not None:
            try:
                claims = decode_access_token(token, settings=api_settings)
                return f"user:{claims.sub}"
            except JwtError:
                pass
    return f"ip:{_client_ip(request)}"


def _storage_uri() -> str:
    # Allow tests to force a clean in-memory backend.
    forced = os.environ.get("API_RATE_LIMIT_STORAGE")
    if forced:
        return forced
    try:
        dsn = get_settings().redis.dsn
        return dsn
    except Exception:  # noqa: BLE001 — defensive: never block import
        return "memory://"


limiter = Limiter(
    key_func=_user_or_ip_key,
    default_limits=["1000/hour", "60/minute"],
    storage_uri=_storage_uri(),
    strategy="moving-window",
    headers_enabled=True,
)


async def _rate_limit_exception_handler(request: Request, exc: RateLimitExceeded) -> Response:
    detail_str = (
        f"Rate limit exceeded: {exc.detail}"
        if getattr(exc, "detail", None)
        else "Rate limit exceeded."
    )
    response = _build(
        status_code=429,
        type_="errors/too-many-requests",
        title="Too Many Requests",
        detail=detail_str,
        request=request,
        extra_headers={"Retry-After": "60"},
    )
    _log.warning(
        "rate_limit_exceeded",
        path=request.url.path,
        client=_client_ip(request),
    )
    return response


def register_rate_limit(app: FastAPI) -> None:
    """Attach the limiter + middleware + exception handler to ``app``."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exception_handler)
    app.add_middleware(SlowAPIMiddleware)


__all__ = ["limiter", "register_rate_limit"]
