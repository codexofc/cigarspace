# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""POST /customs-sources/{code}/refresh-jobs — admin enqueue refresh."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, status

from presentation.api.dependencies import AdminUserDep, UnitOfWorkDep
from presentation.api.hypermedia import make_links
from presentation.api.schemas.base import JobAcceptedResponse


router = APIRouter(prefix="/customs-sources/{code}/refresh-jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a customs source refresh job (admin only).",
)
async def enqueue_refresh_job(
    request: Request,
    admin: AdminUserDep,
    uow: UnitOfWorkDep,
    code: Annotated[str, Path()],
) -> JobAcceptedResponse:
    from arq.connections import create_pool

    from infrastructure.workers.queues import QUEUE_NAME
    from infrastructure.workers.worker import arq_redis_settings

    src = await uow.customs_sources.get_by_code(code)
    if src is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"customs source not found: {code}",
        )

    pool = await create_pool(arq_redis_settings())
    try:
        job = await pool.enqueue_job("refresh_customs_source_job", code, _queue_name=QUEUE_NAME)
    finally:
        await pool.aclose()
    job_id = getattr(job, "job_id", "")
    return JobAcceptedResponse(
        job_id=job_id,
        _links=make_links(request, f"/api/v1/jobs/{job_id}"),
    )
