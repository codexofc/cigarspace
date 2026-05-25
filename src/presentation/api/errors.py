# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""RFC 7807-inspired error response model + global exception handlers."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from infrastructure.observability.logging import get_logger

_log = get_logger("api.errors")


class FieldError(BaseModel):
    """One field-level validation error returned in 422 responses."""

    field: str = Field(description="Dotted path of the offending field.")
    message: str
    code: str | None = None


class ErrorResponse(BaseModel):
    """RFC 7807-style error body returned for every 4xx / 5xx response."""

    type: str = Field(
        description="Stable, URI-like error code (e.g. 'errors/not-found').",
        examples=["errors/not-found"],
    )
    title: str = Field(description="Human-readable summary.")
    status: int = Field(description="HTTP status code.")
    detail: str = Field(description="Detailed, human-readable explanation.")
    instance: str = Field(description="Request path that produced the error (for log correlation).")
    request_id: str = Field(description="Unique ID propagated via the X-Request-Id header.")
    errors: list[FieldError] | None = Field(
        default=None,
        description="Per-field issues (only present on 422 validation errors).",
    )


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "") or str(uuid4())


def _build(
    *,
    status_code: int,
    type_: str,
    title: str,
    detail: str,
    request: Request,
    errors: list[FieldError] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(
        type=type_,
        title=title,
        status=status_code,
        detail=detail,
        instance=str(request.url.path),
        request_id=_request_id(request),
        errors=errors,
    )
    headers = {"X-Request-Id": payload.request_id}
    if extra_headers:
        headers.update(extra_headers)
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload.model_dump(exclude_none=True)),
        headers=headers,
    )


_TITLES: dict[int, tuple[str, str]] = {
    400: ("errors/bad-request", "Bad Request"),
    401: ("errors/unauthorized", "Unauthorized"),
    403: ("errors/forbidden", "Forbidden"),
    404: ("errors/not-found", "Not Found"),
    409: ("errors/conflict", "Conflict"),
    422: ("errors/unprocessable-entity", "Unprocessable Entity"),
    429: ("errors/too-many-requests", "Too Many Requests"),
    500: ("errors/internal-server-error", "Internal Server Error"),
    503: ("errors/service-unavailable", "Service Unavailable"),
}


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    type_, title = _TITLES.get(exc.status_code, ("errors/unknown", "Error"))
    return _build(
        status_code=exc.status_code,
        type_=type_,
        title=title,
        detail=str(exc.detail),
        request=request,
        extra_headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    field_errors = [
        FieldError(
            field=".".join(str(p) for p in err["loc"] if p != "body"),
            message=err["msg"],
            code=err.get("type"),
        )
        for err in exc.errors()
    ]
    return _build(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        type_="errors/unprocessable-entity",
        title="Unprocessable Entity",
        detail="Validation failed for one or more fields.",
        request=request,
        errors=field_errors,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _log.exception(
        "api_unhandled_exception",
        path=str(request.url.path),
        method=request.method,
        error=str(exc),
    )
    return _build(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        type_="errors/internal-server-error",
        title="Internal Server Error",
        detail="An unexpected error occurred. The incident has been logged.",
        request=request,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


__all__ = [
    "ErrorResponse",
    "FieldError",
    "register_exception_handlers",
]
