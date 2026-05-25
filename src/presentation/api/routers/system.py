# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""System endpoints: /health, /version."""

from __future__ import annotations

import subprocess
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import text

from infrastructure.config import get_settings
from presentation.api.dependencies import get_session_factory
from presentation.api.schemas.system import (
    ComponentHealth,
    HealthResponse,
    VersionResponse,
)


router = APIRouter(tags=["System"])


def _alembic_head() -> str | None:
    try:
        out = subprocess.check_output(  # noqa: S603 — local controlled binary
            ["uv", "run", "alembic", "current"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        return out.strip().splitlines()[-1] if out else None
    except Exception:
        return None


def _git_sha() -> str | None:
    try:
        out = subprocess.check_output(  # noqa: S603
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
        return out.strip() or None
    except Exception:
        return None


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Aggregate health check across DB, Redis and S3.",
    description=(
        "Returns 200 with status=`ok` when every dependency responds. "
        "Returns 503 with status=`degraded` or `down` if at least one "
        "dependency is unreachable. Useful for readiness probes."
    ),
)
async def health(
    request: Request,
    response: Response,
    session_factory: Annotated[
        object, Depends(get_session_factory)
    ],  # async_sessionmaker — typed loosely to avoid circular import
) -> HealthResponse:
    settings = get_settings()
    checks: list[ComponentHealth] = []

    # DB
    try:
        async with session_factory() as session:  # type: ignore[operator]
            await session.execute(text("SELECT 1"))
        checks.append(ComponentHealth(name="postgres", status="ok"))
    except Exception as exc:  # noqa: BLE001
        checks.append(ComponentHealth(name="postgres", status="down", detail=str(exc)))

    # Redis (best-effort; lazy import to avoid hard dep at module load)
    try:
        from redis.asyncio import Redis

        redis = Redis.from_url(settings.redis.dsn)
        try:
            await redis.ping()
            checks.append(ComponentHealth(name="redis", status="ok"))
        finally:
            await redis.aclose()
    except Exception as exc:  # noqa: BLE001
        checks.append(ComponentHealth(name="redis", status="down", detail=str(exc)))

    # S3 (best-effort head_bucket)
    try:
        from infrastructure.media.seaweed_storage import SeaweedS3Storage

        storage = SeaweedS3Storage(
            endpoint_url=settings.s3.endpoint_url,
            bucket=settings.s3.bucket,
            access_key_id=settings.s3.access_key_id,
            secret_access_key=settings.s3.secret_access_key,
            region=settings.s3.region,
        )
        try:
            await storage.ensure_bucket()
            checks.append(ComponentHealth(name="s3", status="ok"))
        finally:
            await storage.aclose()
    except Exception as exc:  # noqa: BLE001
        checks.append(ComponentHealth(name="s3", status="degraded", detail=str(exc)))

    overall = "ok"
    if any(c.status == "down" for c in checks):
        overall = "down"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif any(c.status == "degraded" for c in checks):
        overall = "degraded"
        response.status_code = status.HTTP_200_OK
    return HealthResponse(status=overall, checks=checks)


@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Build / schema version metadata.",
)
async def version_endpoint() -> VersionResponse:
    from importlib.metadata import PackageNotFoundError, version as pkg_version

    try:
        v = pkg_version("cigars")
    except PackageNotFoundError:
        v = "0.0.0+local"
    return VersionResponse(
        version=v,
        git_sha=_git_sha(),
        schema_head=_alembic_head(),
    )
