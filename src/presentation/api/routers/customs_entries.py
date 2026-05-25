# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Customs entries endpoint (single resource by id)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request, Response, status

from presentation.api.dependencies import UnitOfWorkDep
from presentation.api.etag import compute_etag, maybe_not_modified
from presentation.api.hypermedia import make_links
from presentation.api.schemas.customs import CustomsEntryResponse


router = APIRouter(prefix="/customs-entries", tags=["Customs Entries"])


@router.get(
    "/{entry_id}",
    response_model=CustomsEntryResponse,
    summary="Retrieve a single customs price entry by UUID.",
)
async def read_entry(
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    entry_id: Annotated[UUID, Path()],
) -> CustomsEntryResponse | Response:
    e = await uow.customs_prices.get_by_id(entry_id)
    if e is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"entry not found: {entry_id}"
        )
    payload = CustomsEntryResponse(
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
            publication=f"/api/v1/customs-publications/{e.publication_id}",
        ),
    )
    etag = compute_etag(payload.model_dump(by_alias=True))
    early = maybe_not_modified(request=request, etag=etag, response=response)
    if early is not None:
        return early
    return payload
