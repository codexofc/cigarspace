# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Customs sources endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, Response, status

from domain.entities.customs import CustomsSource
from presentation.api.dependencies import PaginationDep, UnitOfWorkDep
from presentation.api.etag import compute_etag, maybe_not_modified
from presentation.api.hypermedia import (
    add_pagination_headers,
    make_links,
    make_page_links,
)
from presentation.api.schemas.base import PaginatedResponse
from presentation.api.schemas.customs import CustomsSourceResponse


router = APIRouter(prefix="/customs-sources", tags=["Customs Sources"])


def _to_response(s: CustomsSource, request: Request) -> CustomsSourceResponse:
    return CustomsSourceResponse(
        id=s.id,
        code=s.code,
        country_code=s.country_code,
        display_name=s.display_name,
        index_url=s.index_url,
        discovery_parser_name=s.discovery_parser_name,
        extraction_parser_name=s.extraction_parser_name,
        default_currency_code=s.default_currency_code,
        is_active=s.is_active,
        cron_expression=s.cron_expression,
        last_checked_at=s.last_checked_at,
        last_publication_seen_ref=s.last_publication_seen_ref,
        consecutive_failures=s.consecutive_failures,
        config_json=dict(s.config_json or {}),
        created_at=s.created_at,
        updated_at=s.updated_at,
        _links=make_links(
            request,
            f"/api/v1/customs-sources/{s.code}",
            publications=f"/api/v1/customs-sources/{s.code}/publications",
        ),
    )


@router.get(
    "",
    response_model=PaginatedResponse[CustomsSourceResponse],
    summary="List customs sources (paginated).",
)
async def list_sources(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    paging: PaginationDep,
) -> PaginatedResponse[CustomsSourceResponse]:
    all_sources = list(await uow.customs_sources.list_all())
    total = len(all_sources)
    page_slice = all_sources[paging.offset : paging.offset + paging.limit]
    total_pages = (total + paging.page_size - 1) // paging.page_size

    page_links = make_page_links(
        request,
        path="/api/v1/customs-sources",
        page=paging.page,
        page_size=paging.page_size,
        total_pages=total_pages,
    )
    add_pagination_headers(response, request=request, links=page_links)
    return PaginatedResponse[CustomsSourceResponse](
        items=[_to_response(s, request) for s in page_slice],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
        total_pages=total_pages,
        _links=page_links,
    )


@router.get(
    "/{code}",
    response_model=CustomsSourceResponse,
    summary="Retrieve a customs source by code.",
)
async def read_source(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    code: Annotated[str, Path(description="Source code, e.g. fr-douane-opendata.")],
) -> CustomsSourceResponse | Response:
    src = await uow.customs_sources.get_by_code(code)
    if src is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"customs source not found: {code}",
        )
    payload = _to_response(src, request).model_dump(by_alias=True)
    etag = compute_etag(payload)
    early = maybe_not_modified(request=request, etag=etag, response=response)
    if early is not None:
        return early
    return _to_response(src, request)


@router.get(
    "/{code}/publications",
    response_model=PaginatedResponse,
    summary="List publications of a customs source (paginated).",
)
async def list_publications(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    paging: PaginationDep,
    code: Annotated[str, Path()],
) -> dict:
    from presentation.api.schemas.customs import CustomsPublicationResponse

    src = await uow.customs_sources.get_by_code(code)
    if src is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"source not found: {code}"
        )
    items = list(
        await uow.customs_publications.list_by_source(
            src.id, limit=paging.limit, offset=paging.offset
        )
    )
    total = await uow.customs_publications.count_by_source(src.id)
    total_pages = (total + paging.page_size - 1) // paging.page_size
    page_links = make_page_links(
        request,
        path=f"/api/v1/customs-sources/{code}/publications",
        page=paging.page,
        page_size=paging.page_size,
        total_pages=total_pages,
    )
    add_pagination_headers(response, request=request, links=page_links)
    items_out = [
        CustomsPublicationResponse(
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
                source=f"/api/v1/customs-sources/{code}",
                entries=f"/api/v1/customs-publications/{p.id}/entries",
            ),
        )
        for p in items
    ]
    return PaginatedResponse[CustomsPublicationResponse](
        items=items_out,
        total=total,
        page=paging.page,
        page_size=paging.page_size,
        total_pages=total_pages,
        _links=page_links,
    ).model_dump(by_alias=True)
