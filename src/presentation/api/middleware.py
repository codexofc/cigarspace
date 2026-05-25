# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Request middleware: X-Request-Id, structured access logs, security
headers, gzip compression. CORS and rate-limit are wired in main.py.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

from infrastructure.config.settings import ApiSettings
from infrastructure.observability.logging import get_logger

_REQUEST_ID_HEADER = "X-Request-Id"
_log = get_logger("api.access")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate or propagate a request id and stash it on request.state."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get(_REQUEST_ID_HEADER) or str(uuid4())
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers[_REQUEST_ID_HEADER] = request_id
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """One structured INFO log line per request, with latency in ms."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        started = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            status_code = response.status_code if response is not None else 500
            _log.info(
                "api_request",
                method=request.method,
                path=request.url.path,
                status=status_code,
                duration_ms=duration_ms,
                client=request.client.host if request.client else None,
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add a safe set of response headers (defence-in-depth defaults)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # HSTS only when the request was served over HTTPS (cf. RFC 6797).
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains",
            )
        return response


def register_middleware(app: FastAPI, *, settings: ApiSettings) -> None:
    # Order matters: outermost first → request-id, access log, security
    # headers, gzip (innermost responses are compressed before the
    # outer middlewares observe them).
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIdMiddleware)
