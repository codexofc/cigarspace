# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Media endpoints — list for a cigar + signed download redirect."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Request, status
from fastapi.responses import RedirectResponse

from infrastructure.config import get_settings
from infrastructure.media.seaweed_storage import SeaweedS3Storage
from presentation.api.dependencies import UnitOfWorkDep
from presentation.api.hypermedia import make_links
from presentation.api.schemas.media import MediaAssetResponse

router = APIRouter(tags=["Media"])


async def _signed_url(content_hash: str | None, ext_hint: str = "webp") -> str | None:
    if content_hash is None:
        return None
    settings = get_settings()
    storage = SeaweedS3Storage(
        endpoint_url=settings.s3.endpoint_url,
        bucket=settings.s3.bucket,
        access_key_id=settings.s3.access_key_id,
        secret_access_key=settings.s3.secret_access_key,
        region=settings.s3.region,
    )
    try:
        return await storage.presigned_get(
            content_hash=content_hash, ext=ext_hint, expires_in_seconds=900
        )
    finally:
        await storage.aclose()


@router.get(
    "/cigars/{key}/media",
    response_model=list[MediaAssetResponse],
    summary="List media assets attached to a cigar.",
)
async def list_cigar_media(
    request: Request,
    uow: UnitOfWorkDep,
    key: Annotated[str, Path(description="Cigar slug or UUID.")],
) -> list[MediaAssetResponse]:
    try:
        cigar = await uow.cigars.get_by_id(UUID(key))
    except ValueError:
        cigar = await uow.cigars.get_by_slug(key)
    if cigar is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"cigar not found: {key}")
    assets = await uow.media_assets.find_for_cigar(cigar.id)

    out: list[MediaAssetResponse] = []
    for asset in assets:
        download_url = f"/api/v1/media/{asset.media_blob_hash}" if asset.media_blob_hash else None
        extra: dict[str, str] = {}
        if download_url:
            extra["download"] = download_url
        out.append(
            MediaAssetResponse(
                id=asset.id,
                cigar_id=asset.cigar_id,
                asset_type=asset.asset_type,
                original_url=asset.original_url,
                media_blob_hash=asset.media_blob_hash,
                is_primary=asset.is_primary,
                status=asset.status,
                downloaded_at=asset.downloaded_at,
                created_at=asset.created_at,
                updated_at=asset.updated_at,
                _links=make_links(
                    request,
                    f"/api/v1/cigars/{cigar.slug}/media",
                    cigar=f"/api/v1/cigars/{cigar.slug}",
                    **extra,
                ),
            )
        )
    return out


@router.get(
    "/media/{content_hash}",
    summary="Redirect to a pre-signed download URL for the given blob.",
    description=(
        "Returns a 307 Temporary Redirect to a short-lived (~15 min) "
        "pre-signed URL on the underlying S3-compatible storage."
    ),
    responses={
        307: {"description": "Redirect to signed URL"},
        404: {"description": "Unknown blob"},
    },
)
async def download_media(
    uow: UnitOfWorkDep,
    content_hash: str = Path(min_length=32, max_length=128),
) -> RedirectResponse:
    blob = await uow.media_blobs.get_by_hash(content_hash)
    if blob is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="blob not found")
    url = await _signed_url(blob.content_hash, ext_hint=blob.storage_key.rsplit(".", 1)[-1])
    if url is None:  # defensive — get_by_hash returned a row
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="blob not in storage")
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
