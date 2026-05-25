# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""GET /jobs/{id} — read arq job state from Redis."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, status

from presentation.api.dependencies import AdminUserDep
from presentation.api.hypermedia import make_links
from presentation.api.schemas.job import JobResponse

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Read the status of a background job (admin only).",
)
async def get_job(
    request: Request,
    admin: AdminUserDep,
    job_id: Annotated[str, Path(min_length=1)],
) -> JobResponse:
    from arq.connections import create_pool
    from arq.jobs import Job, JobStatus

    from infrastructure.workers.queues import QUEUE_NAME
    from infrastructure.workers.worker import arq_redis_settings

    pool = await create_pool(arq_redis_settings())
    try:
        job = Job(job_id, pool, _queue_name=QUEUE_NAME)
        try:
            arq_status = await job.status()
        except Exception:  # noqa: BLE001
            arq_status = JobStatus.not_found

        if arq_status == JobStatus.not_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"job not found: {job_id}",
            )

        result: dict | None = None
        error: str | None = None
        if arq_status == JobStatus.complete:
            try:
                info = await job.result_info()
                if info is not None and info.success:
                    result = (
                        info.result if isinstance(info.result, dict) else {"value": info.result}
                    )
                elif info is not None and not info.success:
                    error = str(info.result)
            except Exception:  # noqa: BLE001
                pass
    finally:
        await pool.aclose()

    status_str = {
        JobStatus.deferred: "queued",
        JobStatus.queued: "queued",
        JobStatus.in_progress: "in_progress",
        JobStatus.complete: "complete" if error is None else "failed",
        JobStatus.not_found: "unknown",
    }.get(arq_status, "unknown")

    return JobResponse(
        job_id=job_id,
        status=status_str,  # type: ignore[arg-type]
        result=result,
        error=error,
        _links=make_links(request, f"/api/v1/jobs/{job_id}"),
    )
