# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Cigar packages endpoints (merchant-side packaging variants)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request, status

from presentation.api.dependencies import UnitOfWorkDep
from presentation.api.hypermedia import make_links
from presentation.api.schemas.package import PackageResponse


router = APIRouter(prefix="/cigars/{key}/packages", tags=["Packages"])


@router.get(
    "",
    response_model=list[PackageResponse],
    summary="List merchant packages for a cigar.",
)
async def list_packages(
    request: Request,
    uow: UnitOfWorkDep,
    key: Annotated[str, Path(description="Cigar slug or UUID.")],
) -> list[PackageResponse]:
    try:
        cigar = await uow.cigars.get_by_id(UUID(key))
    except ValueError:
        cigar = await uow.cigars.get_by_slug(key)
    if cigar is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"cigar not found: {key}")
    packages = await uow.cigar_packages.find_for_cigar(cigar.id)
    return [
        PackageResponse(
            id=p.id,
            cigar_id=p.cigar_id,
            pack_size=p.pack_size,
            source_domain=p.source_domain,
            source_url=p.source_url,
            sku=p.sku,
            price_amount=p.price_amount,
            price_currency=p.price_currency,
            is_active=p.is_active,
            last_seen_at=p.last_seen_at,
            created_at=p.created_at,
            updated_at=p.updated_at,
            _links=make_links(
                request,
                f"/api/v1/cigars/{cigar.slug}/packages",
                cigar=f"/api/v1/cigars/{cigar.slug}",
            ),
        )
        for p in packages
    ]
