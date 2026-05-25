# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""POST /match-jobs — admin endpoint to enqueue matcher runs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from presentation.api.dependencies import AdminUserDep, UnitOfWorkDep
from presentation.api.hypermedia import make_links
from presentation.api.schemas.base import JobAcceptedResponse
from presentation.api.schemas.job import MatchJobRequest


router = APIRouter(prefix="/match-jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a matcher job (admin only).",
    description=(
        "Creates a new background job that runs the matcher pipeline. "
        "Use `scope=cigar` + `cigar_id` to re-match a single cigar, or "
        "`scope=all` to fan-out for every cigar with an embedding."
    ),
)
async def enqueue_match_job(
    body: MatchJobRequest,
    request: Request,
    admin: AdminUserDep,
    uow: UnitOfWorkDep,
) -> JobAcceptedResponse:
    from arq.connections import create_pool

    from infrastructure.workers.queues import QUEUE_NAME
    from infrastructure.workers.worker import arq_redis_settings

    if body.scope == "cigar":
        if not body.cigar_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cigar_id is required when scope=cigar",
            )
        try:
            cigar_uuid = UUID(body.cigar_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cigar_id must be a valid UUID",
            )
        if await uow.cigars.get_by_id(cigar_uuid) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"cigar not found: {body.cigar_id}",
            )
        job_name = "match_cigar_job"
        job_args = (str(cigar_uuid),)
    else:
        job_name = "match_all_cigars_job"
        job_args = ()

    pool = await create_pool(arq_redis_settings())
    try:
        job = await pool.enqueue_job(job_name, *job_args, _queue_name=QUEUE_NAME)
    finally:
        await pool.aclose()

    job_id = getattr(job, "job_id", "")
    return JobAcceptedResponse(
        job_id=job_id,
        _links=make_links(
            request,
            f"/api/v1/jobs/{job_id}",
        ),
    )
