# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Brand catalogue endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request, Response, status

from domain.entities.brand import Brand
from presentation.api.dependencies import PaginationDep, UnitOfWorkDep
from presentation.api.etag import compute_etag, maybe_not_modified
from presentation.api.hypermedia import (
    add_pagination_headers,
    make_links,
    make_page_links,
)
from presentation.api.schemas.base import PaginatedResponse
from presentation.api.schemas.brand import BrandResponse
from presentation.api.schemas.line import LineResponse

router = APIRouter(prefix="/brands", tags=["Brands"])


def _to_response(brand: Brand, request: Request) -> BrandResponse:
    return BrandResponse(
        id=brand.id,
        slug=brand.slug,
        name=brand.name,
        country_origin=brand.country_origin,
        parent_company=brand.parent_company,
        founded_year=brand.founded_year,
        is_active=brand.is_active,
        aliases=list(brand.aliases),
        created_at=brand.created_at,
        updated_at=brand.updated_at,
        _links=make_links(
            request,
            f"/api/v1/brands/{brand.slug}",
            lines=f"/api/v1/brands/{brand.slug}/lines",
            cigars=f"/api/v1/cigars?brand_slug={brand.slug}",
        ),
    )


async def _resolve_brand(uow, key: str) -> Brand:
    try:
        brand = await uow.brands.get_by_id(UUID(key))
    except ValueError:
        brand = await uow.brands.get_by_slug(key)
    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"brand not found: {key}",
        )
    return brand


@router.get(
    "",
    response_model=PaginatedResponse[BrandResponse],
    summary="List brands (paginated).",
)
async def list_brands(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    paging: PaginationDep,
) -> PaginatedResponse[BrandResponse]:
    items = list(await uow.brands.list_all(limit=paging.limit, offset=paging.offset))
    total = await uow.brands.count()
    total_pages = (total + paging.page_size - 1) // paging.page_size

    page_links = make_page_links(
        request,
        path="/api/v1/brands",
        page=paging.page,
        page_size=paging.page_size,
        total_pages=total_pages,
    )
    add_pagination_headers(response, request=request, links=page_links)
    return PaginatedResponse[BrandResponse](
        items=[_to_response(b, request) for b in items],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
        total_pages=total_pages,
        _links=page_links,
    )


@router.get(
    "/{key}",
    response_model=BrandResponse,
    summary="Retrieve a brand by slug or UUID.",
    responses={404: {"description": "Brand not found"}, 304: {"description": "Not Modified"}},
)
async def read_brand(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    key: Annotated[str, Path(description="Slug or UUID.")],
) -> BrandResponse | Response:
    brand = await _resolve_brand(uow, key)
    payload = _to_response(brand, request).model_dump(by_alias=True)
    etag = compute_etag(payload)
    early = maybe_not_modified(request=request, etag=etag, response=response)
    if early is not None:
        return early
    return _to_response(brand, request)


@router.get(
    "/{key}/lines",
    response_model=list[LineResponse],
    summary="List lines for a brand.",
)
async def list_brand_lines(
    request: Request,
    uow: UnitOfWorkDep,
    key: Annotated[str, Path(description="Brand slug or UUID.")],
) -> list[LineResponse]:
    brand = await _resolve_brand(uow, key)
    lines = await uow.cigar_lines.list_by_brand(brand.id)
    return [
        LineResponse(
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
        for line in lines
    ]
