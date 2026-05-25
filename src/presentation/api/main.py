# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Public HTTP API entrypoint.

Run locally:
    uv run uvicorn presentation.api.main:app --reload

Or via Docker compose: `docker compose up api`.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from importlib.metadata import PackageNotFoundError, version as _pkg_version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infrastructure.config import get_settings
from infrastructure.matching.sentence_transformer_embedder import (
    SentenceTransformerEmbedder,
)
from infrastructure.observability.logging import configure_logging, get_logger
from infrastructure.persistence.session import build_engine, build_session_factory
from presentation.api.errors import register_exception_handlers
from presentation.api.middleware import register_middleware
from presentation.api.rate_limit import register_rate_limit


_log = get_logger("api.main")


def _resolve_version() -> str:
    try:
        return _pkg_version("cigars")
    except PackageNotFoundError:
        return "0.0.0+local"


_DEFAULT_JWT_SECRETS = frozenset({"change-me", "change-me-in-production", "", "secret"})


def _validate_prod_hardening(env: str, api_settings) -> None:
    """Block ``app.env=prod`` from booting with weak configuration.

    Three checks (CORS=*, default JWT secret, JWT secret < 32 bytes) are
    enforced as RuntimeError because misconfiguring any of them in
    production has far worse consequences than a noisy boot failure.
    """

    if env != "prod":
        return

    problems: list[str] = []
    if "*" in api_settings.cors_origins:
        problems.append("API_CORS_ORIGINS=['*'] is unsafe in prod; list explicit allowed origins.")
    if api_settings.jwt_secret in _DEFAULT_JWT_SECRETS:
        problems.append(
            "API_JWT_SECRET is still a default placeholder; generate a strong secret (≥ 32 bytes)."
        )
    if len(api_settings.jwt_secret.encode("utf-8")) < 32:
        problems.append(
            "API_JWT_SECRET is shorter than 32 bytes; "
            "RFC 7518 §3.2 requires a 256-bit key for HS256."
        )
    if problems:
        joined = "\n  - ".join(problems)
        raise RuntimeError(
            "Refusing to start the API in prod with weak configuration:\n  - " + joined
        )


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    _validate_prod_hardening(settings.app.env, settings.api)

    engine = build_engine()
    session_factory = build_session_factory(engine)
    embedder = SentenceTransformerEmbedder()

    if settings.api.warm_embedder_on_startup:
        _log.info("warming_embedder_model")
        await embedder.encode(["warmup"])  # forces lazy load

    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.embedder = embedder
    app.state.settings = settings

    _log.info(
        "api_started",
        host=settings.api.host,
        port=settings.api.port,
        env=settings.app.env,
    )
    try:
        yield
    finally:
        await engine.dispose()
        _log.info("api_stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    api_settings = settings.api

    app = FastAPI(
        title="Cigarspace API",
        description=(
            "Public read API + protected admin endpoints for the Cigars "
            "Knowledge platform. Authentication uses OAuth2 (RFC 6749) "
            "password / refresh_token grants. All endpoints under "
            "`/api/v1` follow REST conventions (resource nouns, plural, "
            "ETag, pagination, sparse fieldsets, RFC 7807 errors)."
        ),
        version=_resolve_version(),
        openapi_url="/api/v1/openapi.json" if api_settings.docs_enabled else None,
        docs_url="/api/v1/docs" if api_settings.docs_enabled else None,
        redoc_url="/api/v1/redoc" if api_settings.docs_enabled else None,
        lifespan=_lifespan,
        contact={
            "name": "Cigarspace",
            "url": "https://cigars.local/",
        },
        license_info={"name": "Proprietary"},
        openapi_tags=[
            {"name": "OAuth", "description": "RFC 6749 token issuance + revocation."},
            {"name": "Users", "description": "Authenticated user profile."},
            {"name": "Brands", "description": "Cigar brands."},
            {"name": "Lines", "description": "Brand product lines."},
            {"name": "Cigars", "description": "Canonical cigars catalogue."},
            {"name": "Search", "description": "Hybrid full-text + vector search."},
            {"name": "Packages", "description": "Merchant packaging variants."},
            {"name": "Media", "description": "Image assets (signed S3 URLs)."},
            {"name": "Customs Sources", "description": "Regulatory sources."},
            {"name": "Customs Publications", "description": "Per-arrêté documents."},
            {"name": "Customs Entries", "description": "Per-row price entries."},
            {"name": "Matches", "description": "Cigar↔customs match decisions."},
            {"name": "Jobs", "description": "Background-job sub-resources."},
            {"name": "System", "description": "Health & version."},
        ],
    )

    register_middleware(app, settings=api_settings)

    # CORS — defaults are permissive in dev; the lifespan guards prod.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id", "ETag", "Link", "Retry-After"],
    )

    # Rate-limit middleware. Uses Redis when reachable; falls back to an
    # in-memory store otherwise (fine for single-worker dev / tests).
    register_rate_limit(app)

    register_exception_handlers(app)

    # Routers are imported lazily so module-import order can't bite us at
    # cold start, and tests can monkey-patch dependencies before routes
    # are wired.
    from presentation.api.routers import register_routers

    register_routers(app)

    return app


# Module-level instance for ``uvicorn presentation.api.main:app``.
app = create_app()
