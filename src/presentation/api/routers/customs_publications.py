# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Customs publications endpoints (single resource + nested entries)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request, Response, status

from presentation.api.dependencies import PaginationDep, UnitOfWorkDep
from presentation.api.etag import compute_etag, maybe_not_modified
from presentation.api.hypermedia import (
    add_pagination_headers,
    make_links,
    make_page_links,
)
from presentation.api.schemas.base import PaginatedResponse
from presentation.api.schemas.customs import (
    CustomsEntryResponse,
    CustomsPublicationResponse,
)


router = APIRouter(prefix="/customs-publications", tags=["Customs Publications"])


@router.get(
    "/{publication_id}",
    response_model=CustomsPublicationResponse,
    summary="Retrieve a customs publication by UUID.",
)
async def read_publication(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    publication_id: Annotated[UUID, Path()],
) -> CustomsPublicationResponse | Response:
    p = await uow.customs_publications.get_by_id(publication_id)
    if p is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"publication not found: {publication_id}",
        )
    source = await uow.customs_sources.get_by_id(p.source_id)
    source_link = (
        f"/api/v1/customs-sources/{source.code}"
        if source
        else f"/api/v1/customs-sources/{p.source_id}"
    )
    payload = CustomsPublicationResponse(
        id=p.id,
        source_id=p.source_id,
        regulator_reference=p.regulator_reference,
        publication_date=p.publication_date,
        effective_date=p.effective_date,
        document_url=p.document_url,
        document_mime=p.document_mime,
        content_hash=p.content_hash,
        status=p.status,
        fetched_at=p.fetched_at,
        parsed_at=p.parsed_at,
        failure_reason=p.failure_reason,
        entries_count=p.entries_count,
        created_at=p.created_at,
        updated_at=p.updated_at,
        _links=make_links(
            request,
            f"/api/v1/customs-publications/{p.id}",
            source=source_link,
            entries=f"/api/v1/customs-publications/{p.id}/entries",
        ),
    )
    etag = compute_etag(payload.model_dump(by_alias=True))
    early = maybe_not_modified(request=request, etag=etag, response=response)
    if early is not None:
        return early
    return payload


@router.get(
    "/{publication_id}/entries",
    response_model=PaginatedResponse[CustomsEntryResponse],
    summary="List price entries belonging to a publication (paginated).",
)
async def list_entries(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    paging: PaginationDep,
    publication_id: Annotated[UUID, Path()],
) -> PaginatedResponse[CustomsEntryResponse]:
    if await uow.customs_publications.get_by_id(publication_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"publication not found: {publication_id}",
        )
    entries = list(
        await uow.customs_prices.list_by_publication(
            publication_id, limit=paging.limit, offset=paging.offset
        )
    )
    total = await uow.customs_prices.count_by_publication(publication_id)
    total_pages = (total + paging.page_size - 1) // paging.page_size
    page_links = make_page_links(
        request,
        path=f"/api/v1/customs-publications/{publication_id}/entries",
        page=paging.page,
        page_size=paging.page_size,
        total_pages=total_pages,
    )
    add_pagination_headers(response, request=request, links=page_links)
    return PaginatedResponse[CustomsEntryResponse](
        items=[
            CustomsEntryResponse(
                id=e.id,
                publication_id=e.publication_id,
                country_code=e.country_code,
                currency_code=e.currency_code,
                unit_price=e.unit_price,
                homologation_date=e.homologation_date,
                effective_date=e.effective_date,
                raw_brand_label=e.raw_brand_label,
                raw_product_label=e.raw_product_label,
                packaging_description=e.packaging_description,
                pack_size=e.pack_size,
                unit_count=e.unit_count,
                tax_class=e.tax_class,
                extracted_at=e.extracted_at,
                extractor_version=e.extractor_version,
                created_at=e.created_at,
                updated_at=e.updated_at,
                _links=make_links(
                    request,
                    f"/api/v1/customs-entries/{e.id}",
                    publication=f"/api/v1/customs-publications/{publication_id}",
                ),
            )
            for e in entries
        ],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
        total_pages=total_pages,
        _links=page_links,
    )
