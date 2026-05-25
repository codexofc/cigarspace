# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Cigar catalogue endpoints + hybrid search."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status

from application.ports.cigar_repository import CigarFilters, CigarSort
from domain.entities.cigar import Cigar
from domain.enums import CustomsMatchStatus, FormatCategory, Intensity
from presentation.api.dependencies import (
    PaginationDep,
    UnitOfWorkDep,
    get_embedder,
)
from presentation.api.etag import compute_etag, maybe_not_modified
from presentation.api.hypermedia import (
    add_pagination_headers,
    make_links,
    make_page_links,
)
from presentation.api.schemas.base import PaginatedResponse
from presentation.api.schemas.cigar import (
    BlendComponentResponse,
    CigarResponse,
    CigarSummary,
)
from presentation.api.schemas.search import SearchHit, SearchResponse

router = APIRouter(prefix="/cigars", tags=["Cigars"])


def _to_summary(c: Cigar, request: Request) -> CigarSummary:
    return CigarSummary(
        id=c.id,
        slug=c.slug,
        full_name=c.full_name,
        vitola_name=c.vitola_name,
        format_category=c.format_category,
        is_cuban=c.is_cuban,
        _links=make_links(request, f"/api/v1/cigars/{c.slug}"),
    )


def _to_response(c: Cigar, request: Request) -> CigarResponse:
    return CigarResponse(
        id=c.id,
        line_id=c.line_id,
        slug=c.slug,
        full_name=c.full_name,
        vitola_name=c.vitola_name,
        vitola_factory_name=c.vitola_factory_name,
        format_category=c.format_category,
        length_mm=c.length_mm,
        ring_gauge=c.ring_gauge,
        ring_gauge_mm=c.ring_gauge_mm,
        weight_g=c.weight_g,
        draw_resistance_cmh2o=c.draw_resistance_cmh2o,
        wrapper_country=c.wrapper_country,
        binder_country=c.binder_country,
        filler_countries=list(c.filler_countries),
        strength=c.strength,
        body=c.body,
        flavor_profile=c.flavor_profile.model_dump(exclude_none=True),
        aging_potential_years=c.aging_potential_years,
        is_cuban=c.is_cuban,
        is_handmade=c.is_handmade,
        is_box_pressed=c.is_box_pressed,
        release_year=c.release_year,
        discontinued_year=c.discontinued_year,
        blend_components=[
            BlendComponentResponse(
                component_type=b.component_type,
                tobacco_origin=b.tobacco_origin,
                tobacco_region=b.tobacco_region,
                tobacco_variety=b.tobacco_variety,
                aging_years=b.aging_years,
                percentage=b.percentage,
                source_confidence=b.source_confidence,
            )
            for b in c.blend_components
        ],
        last_scraped_at=c.last_scraped_at,
        created_at=c.created_at,
        updated_at=c.updated_at,
        _links=make_links(
            request,
            f"/api/v1/cigars/{c.slug}",
            line=f"/api/v1/lines/{c.line_id}",
            packages=f"/api/v1/cigars/{c.slug}/packages",
            media=f"/api/v1/cigars/{c.slug}/media",
            customs_matches=f"/api/v1/cigars/{c.slug}/customs-matches",
        ),
    )


async def _resolve_cigar(uow, key: str) -> Cigar:
    try:
        cigar = await uow.cigars.get_by_id(UUID(key))
    except ValueError:
        cigar = await uow.cigars.get_by_slug(key)
    if cigar is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"cigar not found: {key}")
    return cigar


_ALLOWED_SORT_FIELDS = {"created_at", "full_name", "length_mm", "ring_gauge"}


def _parse_sort(sort: str | None) -> CigarSort:
    if not sort:
        return CigarSort(field="created_at", descending=True)
    field = sort.lstrip("-")
    if field not in _ALLOWED_SORT_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"unknown sort field '{field}'. Allowed: {sorted(_ALLOWED_SORT_FIELDS)}"),
        )
    return CigarSort(field=field, descending=sort.startswith("-"))


@router.get(
    "",
    response_model=PaginatedResponse[CigarSummary],
    summary="List cigars (paginated, filterable).",
)
async def list_cigars(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    paging: PaginationDep,
    brand: str | None = Query(None, description="Filter by brand slug."),
    format: FormatCategory | None = Query(None, description="Filter by format."),
    is_cuban: bool | None = Query(None, description="Filter Cuban / non-Cuban."),
    is_handmade: bool | None = Query(None),
    country_origin: str | None = Query(
        None, description="Filter by brand country (ISO 3166-1 alpha-3)."
    ),
    strength: Intensity | None = Query(None),
    min_length_mm: float | None = Query(None, ge=0),
    max_length_mm: float | None = Query(None, ge=0),
    min_ring_gauge: int | None = Query(None, ge=20, le=80),
    max_ring_gauge: int | None = Query(None, ge=20, le=80),
    sort: str | None = Query(
        None,
        description=(
            "Sort field; prefix with `-` for descending. "
            "Allowed: created_at, full_name, length_mm, ring_gauge."
        ),
    ),
) -> PaginatedResponse[CigarSummary]:
    from decimal import Decimal as _D

    filters = CigarFilters(
        brand_slug=brand,
        format_category=format,
        is_cuban=is_cuban,
        is_handmade=is_handmade,
        country_origin=country_origin,
        strength=strength,
        min_length_mm=_D(str(min_length_mm)) if min_length_mm is not None else None,
        max_length_mm=_D(str(max_length_mm)) if max_length_mm is not None else None,
        min_ring_gauge=min_ring_gauge,
        max_ring_gauge=max_ring_gauge,
    )
    sort_spec = _parse_sort(sort)

    items = list(
        await uow.cigars.list_filtered(
            filters=filters, sort=sort_spec, limit=paging.limit, offset=paging.offset
        )
    )
    total = await uow.cigars.count_filtered(filters)
    total_pages = (total + paging.page_size - 1) // paging.page_size

    extra_query: dict = {}
    if brand:
        extra_query["brand"] = brand
    if format:
        extra_query["format"] = format.value
    if is_cuban is not None:
        extra_query["is_cuban"] = str(is_cuban).lower()
    if sort:
        extra_query["sort"] = sort

    page_links = make_page_links(
        request,
        path="/api/v1/cigars",
        page=paging.page,
        page_size=paging.page_size,
        total_pages=total_pages,
        extra_query=extra_query,
    )
    add_pagination_headers(response, request=request, links=page_links)
    return PaginatedResponse[CigarSummary](
        items=[_to_summary(c, request) for c in items],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
        total_pages=total_pages,
        _links=page_links,
    )


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Hybrid full-text + vector search.",
    description=(
        "Combines a pg_trgm full-text branch and an mpnet vector recall "
        "branch via Reciprocal Rank Fusion. Higher scores indicate the "
        "cigar surfaced near the top of multiple branches."
    ),
)
async def search_cigars(
    request: Request,
    uow: UnitOfWorkDep,
    embedder=Depends(get_embedder),
    q: str = Query(..., min_length=2, max_length=200, description="Search text."),
    limit: int = Query(20, ge=1, le=50),
) -> SearchResponse:
    from application.use_cases.hybrid_search import HybridSearchUseCase

    use_case = HybridSearchUseCase(embedder=embedder)
    hits = await use_case.execute(query=q, uow=uow, limit=limit)
    return SearchResponse(
        query=q,
        total=len(hits),
        items=[
            SearchHit(
                cigar=_to_summary(hit.cigar, request),
                score=hit.score,
                matched_by=list(hit.matched_by),
            )
            for hit in hits
        ],
    )


@router.get(
    "/{key}",
    response_model=CigarResponse,
    summary="Retrieve a cigar by slug or UUID.",
)
async def read_cigar(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    key: Annotated[str, Path(description="Slug or UUID.")],
) -> CigarResponse | Response:
    cigar = await _resolve_cigar(uow, key)
    payload = _to_response(cigar, request).model_dump(by_alias=True)
    etag = compute_etag(payload)
    early = maybe_not_modified(request=request, etag=etag, response=response)
    if early is not None:
        return early
    return _to_response(cigar, request)


@router.get(
    "/{key}/customs-matches",
    response_model=list,
    summary="List accepted customs matches for a cigar (AUTO/HUMAN accepted).",
)
async def list_customs_matches(
    request: Request,
    uow: UnitOfWorkDep,
    key: Annotated[str, Path(description="Cigar slug or UUID.")],
) -> list[dict]:
    from presentation.api.schemas.match import MatchResponse

    cigar = await _resolve_cigar(uow, key)
    matches = await uow.customs_matches.find_for_cigar(cigar.id)
    accepted = {
        CustomsMatchStatus.AUTO_ACCEPTED,
        CustomsMatchStatus.HUMAN_ACCEPTED,
    }
    return [
        MatchResponse(
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
                cigar=f"/api/v1/cigars/{cigar.slug}",
                customs_entry=f"/api/v1/customs-entries/{m.customs_entry_id}",
            ),
        ).model_dump(by_alias=True)
        for m in matches
        if m.status in accepted
    ]
