# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Cigar-customs match endpoints (read + admin PATCH transition)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response, status

from domain.enums import CustomsMatchStatus
from presentation.api.dependencies import (
    AdminUserDep,
    CurrentUserDep,
    PaginationDep,
    UnitOfWorkDep,
)
from presentation.api.etag import compute_etag, maybe_not_modified
from presentation.api.hypermedia import (
    add_pagination_headers,
    make_links,
    make_page_links,
)
from presentation.api.schemas.base import PaginatedResponse
from presentation.api.schemas.match import MatchPatchRequest, MatchResponse

router = APIRouter(prefix="/matches", tags=["Matches"])


_PUBLIC_STATUSES = {
    CustomsMatchStatus.AUTO_ACCEPTED,
    CustomsMatchStatus.HUMAN_ACCEPTED,
}


def _to_response(m, request: Request) -> MatchResponse:
    return MatchResponse(
        id=m.id,
        cigar_id=m.cigar_id,
        customs_entry_id=m.customs_entry_id,
        match_method=m.match_method,
        score=m.score,
        confidence=m.confidence,
        status=m.status,
        pack_size_bucket=m.pack_size_bucket,
        signals=dict(m.signals or {}),
        matched_at=m.matched_at,
        matched_by=m.matched_by,
        reviewed_by=m.reviewed_by,
        reviewed_at=m.reviewed_at,
        notes=m.notes,
        created_at=m.created_at,
        updated_at=m.updated_at,
        _links=make_links(
            request,
            f"/api/v1/matches/{m.id}",
            cigar=f"/api/v1/cigars/{m.cigar_id}",
            customs_entry=f"/api/v1/customs-entries/{m.customs_entry_id}",
        ),
    )


@router.get(
    "",
    response_model=PaginatedResponse[MatchResponse],
    summary="List matches (paginated, filterable by status).",
    description=(
        "Anonymous and read-scoped users only see `auto_accepted` and "
        "`human_accepted` matches. Admin users may filter on any status, "
        "including the `pending_review` queue."
    ),
)
async def list_matches(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    paging: PaginationDep,
    user: CurrentUserDep,
    status_filter: Annotated[
        list[CustomsMatchStatus] | None,
        Query(
            alias="status",
            description="Filter by status (multiple allowed).",
        ),
    ] = None,
) -> PaginatedResponse[MatchResponse]:
    requested = set(status_filter) if status_filter else set(CustomsMatchStatus)
    if not user.is_admin:
        # Non-admin users may only see accepted matches.
        requested &= _PUBLIC_STATUSES
        if not requested:
            requested = _PUBLIC_STATUSES
    items = list(
        await uow.customs_matches.list_by_statuses(
            list(requested), limit=paging.limit, offset=paging.offset
        )
    )
    total = await uow.customs_matches.count_by_statuses(list(requested))
    total_pages = (total + paging.page_size - 1) // paging.page_size
    page_links = make_page_links(
        request,
        path="/api/v1/matches",
        page=paging.page,
        page_size=paging.page_size,
        total_pages=total_pages,
        extra_query=({"status": ",".join(s.value for s in requested)} if status_filter else None),
    )
    add_pagination_headers(response, request=request, links=page_links)
    return PaginatedResponse[MatchResponse](
        items=[_to_response(m, request) for m in items],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
        total_pages=total_pages,
        _links=page_links,
    )


@router.get(
    "/{match_id}",
    response_model=MatchResponse,
    summary="Retrieve a single match by id.",
)
async def read_match(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    user: CurrentUserDep,
    match_id: Annotated[UUID, Path()],
) -> MatchResponse | Response:
    m = await uow.customs_matches.get_by_id(match_id)
    if m is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"match not found: {match_id}"
        )
    if not user.is_admin and m.status not in _PUBLIC_STATUSES:
        # Hide pending/rejected matches from non-admins (404 to avoid
        # leaking existence).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"match not found: {match_id}"
        )
    payload = _to_response(m, request).model_dump(by_alias=True)
    etag = compute_etag(payload)
    early = maybe_not_modified(request=request, etag=etag, response=response)
    if early is not None:
        return early
    return _to_response(m, request)


@router.patch(
    "/{match_id}",
    response_model=MatchResponse,
    summary="Apply a human decision to a match (admin only).",
    description=(
        "Sets the match status to either `human_accepted` or "
        "`human_rejected`. Subsequent runs of the matcher will preserve "
        "this verdict and never overwrite it."
    ),
)
async def patch_match(
    request: Request,
    uow: UnitOfWorkDep,
    admin: AdminUserDep,
    body: MatchPatchRequest,
    match_id: Annotated[UUID, Path()],
) -> MatchResponse:
    if await uow.customs_matches.get_by_id(match_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"match not found: {match_id}"
        )
    updated = await uow.customs_matches.apply_human_decision(
        match_id,
        accepted=body.status == "human_accepted",
        reviewer=admin.email,
        notes=body.notes,
    )
    await uow.commit()
    return _to_response(updated, request)
