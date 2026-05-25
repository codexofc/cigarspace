# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""End-to-end tests for download_media_job.

Uses a canned fetcher (synthesised PNG bytes) and a fake in-memory
storage so the job runs without hitting the network or SeaweedFS.
Real SeaweedFS interaction is covered by smoke tests (network marker).
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.fetcher import FetchError, FetchRequest, FetchResponse
from domain.entities.brand import Brand
from domain.entities.cigar import Cigar
from domain.entities.cigar_line import CigarLine
from domain.entities.media import MediaAsset
from domain.enums import MediaAssetType, MediaStatus
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from infrastructure.workers.jobs import download_media_job

pytestmark = pytest.mark.integration

PNG_URL = "https://example.com/cohiba.png"
JPG_URL = "https://example.com/padron.jpg"


def _make_png(w: int = 320, h: int = 240, color: tuple[int, int, int] = (200, 50, 50)) -> bytes:
    img = Image.new("RGB", (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _MultiFetcher:
    def __init__(self, mapping: dict[str, bytes | BaseException]) -> None:
        self._mapping = mapping

    async def fetch(self, req: FetchRequest) -> FetchResponse:
        v = self._mapping[req.url]
        if isinstance(v, BaseException):
            raise v
        return FetchResponse(
            url=req.url,
            status_code=200,
            headers={"content-type": "image/png"},
            body=v,
            elapsed_s=0.01,
            fetched_at=datetime.now(tz=timezone.utc),
        )

    async def aclose(self) -> None:
        return None


class _FakeStorage:
    def __init__(self) -> None:
        self.puts: list[tuple[str, str, int]] = []  # (key, mime, size)

    async def put(self, *, content_hash: str, data: bytes, ext: str, mime_type: str) -> str:
        key = f"{content_hash[:2]}/{content_hash}.{ext}"
        self.puts.append((key, mime_type, len(data)))
        return key

    async def exists(self, *, storage_key: str) -> bool:
        return any(k == storage_key for k, _, _ in self.puts)

    async def public_url(self, *, storage_key: str) -> str:
        return f"http://fake/{storage_key}"

    async def aclose(self) -> None:
        return None


async def _seed_cigar_with_asset(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    url: str,
    slug: str = "test-cigar",
) -> UUID:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        brand = await uow.brands.add(Brand(slug=f"{slug}-brand", name="TestBrand"))
        line = await uow.cigar_lines.add(
            CigarLine(brand_id=brand.id, slug=f"{slug}-brand", name="TestBrand")
        )
        cigar = await uow.cigars.add(
            Cigar(
                line_id=line.id,
                slug=slug,
                full_name="Test Cigar",
                vitola_name="Robusto",
            )
        )
        asset = await uow.media_assets.add(
            MediaAsset(
                cigar_id=cigar.id,
                asset_type=MediaAssetType.FRONT,
                original_url=url,
                is_primary=True,
                status=MediaStatus.PENDING,
            )
        )
        await uow.commit()
        return asset.id


def _ctx(
    fetcher: _MultiFetcher,
    storage: _FakeStorage,
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    return {"fetcher": fetcher, "storage": storage, "session_factory": session_factory}


async def test_happy_path_uploads_and_links(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    png = _make_png()
    asset_id = await _seed_cigar_with_asset(session_factory, url=PNG_URL)
    fetcher = _MultiFetcher({PNG_URL: png})
    storage = _FakeStorage()
    ctx = _ctx(fetcher, storage, session_factory)

    result = await download_media_job(ctx, str(asset_id))

    assert result["status"] == "downloaded"
    assert "content_hash" in result
    assert len(storage.puts) == 1

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        asset = await uow.media_assets.get_by_id(asset_id)
        blob = await uow.media_blobs.get_by_hash(result["content_hash"])
    assert asset is not None
    assert asset.status is MediaStatus.OK
    assert asset.media_blob_hash == result["content_hash"]
    assert asset.downloaded_at is not None
    assert blob is not None
    assert blob.mime_type == "image/webp"
    assert blob.byte_size > 0


async def test_dedup_skips_upload_when_blob_exists(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    # Two distinct cigars / assets pointing at URLs that yield IDENTICAL bytes
    # (after normalisation → same hash). Second call must NOT re-upload.
    png = _make_png(color=(10, 200, 30))
    asset_a = await _seed_cigar_with_asset(session_factory, url=PNG_URL, slug="cigar-a")
    asset_b = await _seed_cigar_with_asset(session_factory, url=JPG_URL, slug="cigar-b")

    fetcher = _MultiFetcher({PNG_URL: png, JPG_URL: png})
    storage = _FakeStorage()
    ctx = _ctx(fetcher, storage, session_factory)

    res_a = await download_media_job(ctx, str(asset_a))
    res_b = await download_media_job(ctx, str(asset_b))

    assert res_a["status"] == "downloaded"
    assert res_b["status"] == "dedup"
    assert res_a["content_hash"] == res_b["content_hash"]
    assert len(storage.puts) == 1  # second call did not upload again

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        a = await uow.media_assets.get_by_id(asset_a)
        b = await uow.media_assets.get_by_id(asset_b)
    assert a is not None and b is not None
    assert a.media_blob_hash == b.media_blob_hash  # both linked to same blob
    assert a.status is MediaStatus.OK
    assert b.status is MediaStatus.OK


async def test_fetch_failure_marks_failed(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    asset_id = await _seed_cigar_with_asset(session_factory, url=PNG_URL)
    fetcher = _MultiFetcher({PNG_URL: FetchError("boom")})
    storage = _FakeStorage()
    ctx = _ctx(fetcher, storage, session_factory)

    result = await download_media_job(ctx, str(asset_id))

    assert result["status"] == "fetch_failed"
    assert storage.puts == []
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        asset = await uow.media_assets.get_by_id(asset_id)
    assert asset is not None
    assert asset.status is MediaStatus.FAILED


async def test_invalid_image_marks_quarantined(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    asset_id = await _seed_cigar_with_asset(session_factory, url=PNG_URL)
    fetcher = _MultiFetcher({PNG_URL: b"definitely not an image " * 100})
    storage = _FakeStorage()
    ctx = _ctx(fetcher, storage, session_factory)

    result = await download_media_job(ctx, str(asset_id))

    assert result["status"] == "invalid"
    assert storage.puts == []
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        asset = await uow.media_assets.get_by_id(asset_id)
    assert asset is not None
    assert asset.status is MediaStatus.QUARANTINED


async def test_already_ok_is_noop(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    asset_id = await _seed_cigar_with_asset(session_factory, url=PNG_URL)
    fetcher = _MultiFetcher({PNG_URL: _make_png()})
    storage = _FakeStorage()
    ctx = _ctx(fetcher, storage, session_factory)

    first = await download_media_job(ctx, str(asset_id))
    assert first["status"] == "downloaded"

    # Re-run on the same already-OK asset → no-op
    second = await download_media_job(ctx, str(asset_id))
    assert second["status"] == "already_ok"
    assert len(storage.puts) == 1


async def test_unknown_asset_returns_not_found(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    fetcher = _MultiFetcher({})
    storage = _FakeStorage()
    ctx = _ctx(fetcher, storage, session_factory)
    result = await download_media_job(ctx, "11111111-1111-1111-1111-111111111111")
    assert result["status"] == "not_found"


async def test_bad_asset_id_format() -> None:
    result = await download_media_job(
        {"fetcher": None, "storage": None, "session_factory": None}, "not-a-uuid"
    )
    assert result["status"] == "bad_id"
