# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Mount all routers under /api/v1.

Each router lives in its own module and is added here explicitly so the
URL surface is auditable in one place.
"""

from __future__ import annotations

from fastapi import FastAPI

from presentation.api.routers import (
    auth_web,
    brands,
    cigars,
    customs_entries,
    customs_publications,
    customs_sources,
    jobs,
    lines,
    match_jobs,
    matches,
    media,
    oauth,
    packages,
    refresh_jobs,
    system,
    users,
)

_PREFIX = "/api/v1"


def register_routers(app: FastAPI) -> None:
    app.include_router(oauth.router, prefix=_PREFIX)
    app.include_router(auth_web.router, prefix=_PREFIX)
    app.include_router(users.router, prefix=_PREFIX)
    app.include_router(brands.router, prefix=_PREFIX)
    app.include_router(lines.router, prefix=_PREFIX)
    app.include_router(cigars.router, prefix=_PREFIX)
    app.include_router(packages.router, prefix=_PREFIX)
    app.include_router(media.router, prefix=_PREFIX)
    app.include_router(customs_sources.router, prefix=_PREFIX)
    app.include_router(customs_publications.router, prefix=_PREFIX)
    app.include_router(customs_entries.router, prefix=_PREFIX)
    app.include_router(matches.router, prefix=_PREFIX)
    app.include_router(match_jobs.router, prefix=_PREFIX)
    app.include_router(refresh_jobs.router, prefix=_PREFIX)
    app.include_router(jobs.router, prefix=_PREFIX)
    app.include_router(system.router, prefix=_PREFIX)
