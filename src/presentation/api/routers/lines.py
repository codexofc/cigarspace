# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""CigarLine catalogue endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request, status

from domain.entities.cigar_line import CigarLine
from presentation.api.dependencies import UnitOfWorkDep
from presentation.api.hypermedia import make_links
from presentation.api.schemas.cigar import CigarSummary
from presentation.api.schemas.line import LineResponse


router = APIRouter(prefix="/lines", tags=["Lines"])


async def _resolve_line(uow, key: str) -> CigarLine:
    try:
        line = await uow.cigar_lines.get_by_id(UUID(key))
    except ValueError:
        line = await uow.cigar_lines.get_by_slug_global(key)
    if line is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"line not found: {key}")
    return line


@router.get(
    "/{key}",
    response_model=LineResponse,
    summary="Retrieve a line by slug or UUID.",
)
async def read_line(
    request: Request,
    uow: UnitOfWorkDep,
    key: Annotated[str, Path(description="Slug or UUID.")],
) -> LineResponse:
    line = await _resolve_line(uow, key)
    brand = await uow.brands.get_by_id(line.brand_id)
    assert brand is not None
    return LineResponse(
        id=line.id,
        brand_id=line.brand_id,
        slug=line.slug,
        name=line.name,
        release_year=line.release_year,
        is_limited_edition=line.is_limited_edition,
        description=line.description,
        aliases=list(line.aliases),
        created_at=line.created_at,
        updated_at=line.updated_at,
        _links=make_links(
            request,
            f"/api/v1/lines/{line.slug}",
            brand=f"/api/v1/brands/{brand.slug}",
            cigars=f"/api/v1/lines/{line.slug}/cigars",
        ),
    )


@router.get(
    "/{key}/cigars",
    response_model=list[CigarSummary],
    summary="List cigars belonging to a line.",
)
async def list_cigars_for_line(
    request: Request,
    uow: UnitOfWorkDep,
    key: Annotated[str, Path(description="Slug or UUID.")],
) -> list[CigarSummary]:
    line = await _resolve_line(uow, key)
    cigars = await uow.cigars.list_by_line(line.id)
    return [
        CigarSummary(
            id=c.id,
            slug=c.slug,
            full_name=c.full_name,
            vitola_name=c.vitola_name,
            format_category=c.format_category,
            is_cuban=c.is_cuban,
            _links=make_links(request, f"/api/v1/cigars/{c.slug}"),
        )
        for c in cigars
    ]
