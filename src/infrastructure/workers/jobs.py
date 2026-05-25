# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""arq job functions — async, parameterised by ctx['fetcher','session_factory'].

Jobs registered here:
- ingest_product_job  : URL → upsert (Brand, Line, Cigar, Package, Media…)
- crawl_listing_job   : URL listing → enqueue 1 ingest_product_job per
                        product + re-enqueue itself with the next page
- download_media_stub_job : placeholder for the media pipeline (just logs
                        the asset_id)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from application.ports.fetcher import FetchError, FetchRequest
from application.use_cases.build_embeddings import BuildEmbeddingsUseCase
from application.use_cases.ingest_customs_publication import (
    IngestCustomsPublicationUseCase,
)
from application.use_cases.ingest_product import (
    IngestProductUrlUseCase,
)
from application.use_cases.match_cigar_to_customs import MatchCigarToCustomsUseCase
from application.use_cases.refresh_customs_source import RefreshCustomsSourceUseCase
from domain.entities.media_blob import MediaBlob
from domain.enums import MediaStatus
from infrastructure.config import get_settings
from infrastructure.media.errors import ImageValidationError, StorageError
from infrastructure.media.hashing import blake3_hex
from infrastructure.media.image_pipeline import validate_and_normalize
from infrastructure.observability.logging import get_logger
from infrastructure.parsers import (
    listing_parser_for_url,
    product_parser_for_url,
)
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from infrastructure.workers.queues import QUEUE_NAME

# ---------------------------------------------------------------------------


async def ingest_product_job(ctx: dict[str, Any], url: str) -> dict[str, Any]:
    """Fetch one product page and persist its cigar/package/media records.

    On CREATED, enqueue download_media_job for any PENDING MediaAsset of
    the cigar (typically the primary front image extracted by the parser).
    """

    log = get_logger("job.ingest_product")
    use_case = IngestProductUrlUseCase(
        fetcher=ctx["fetcher"],
        parser=product_parser_for_url(url),
    )
    async with SqlAlchemyUnitOfWork(ctx["session_factory"]) as uow:
        result = await use_case.execute(url=url, uow=uow)

    # Enqueue media downloads for any PENDING asset of this cigar
    enqueued_media = 0
    redis = ctx.get("redis")
    if redis is not None:
        async with SqlAlchemyUnitOfWork(ctx["session_factory"]) as uow:
            for asset in await uow.media_assets.find_for_cigar(result.cigar.id):
                if asset.status.value == "pending" and asset.media_blob_hash is None:
                    await redis.enqueue_job(
                        "download_media_job",
                        str(asset.id),
                        _queue_name=QUEUE_NAME,
                    )
                    enqueued_media += 1

    payload = {
        "outcome": result.outcome.value,
        "cigar_id": str(result.cigar.id),
        "slug": result.cigar.slug,
        "media_enqueued": enqueued_media,
    }
    log.info("ingest_product_done", url=url, **payload)
    return payload


# ---------------------------------------------------------------------------


async def crawl_listing_job(
    ctx: dict[str, Any],
    start_url: str,
    max_pages: int = 5,
    max_products: int | None = None,
    _page_n: int = 1,
    _processed: int = 0,
) -> dict[str, Any]:
    """Walk a category listing page, enqueue 1 ingest_product_job per product.

    Re-enqueues itself with the next page URL until max_pages or the
    pagination is exhausted. State carried across enqueues via the private
    `_page_n` and `_processed` kwargs (underscore-prefixed = internal).
    """

    log = get_logger("job.crawl_listing")
    if _page_n > max_pages:
        log.info("crawl_stop_max_pages", start_url=start_url, page_n=_page_n)
        return {"stop": "max_pages", "page_n": _page_n}

    fetcher = ctx["fetcher"]
    redis = ctx["redis"]
    parser = listing_parser_for_url(start_url)

    response = await fetcher.fetch(FetchRequest(url=start_url, timeout_s=30))
    listing = parser.parse_listing(html=response.text, page_url=start_url)

    enqueued = 0
    for product_url in listing.product_urls:
        if max_products is not None and (_processed + enqueued) >= max_products:
            log.info(
                "crawl_stop_max_products",
                start_url=start_url,
                processed=_processed + enqueued,
            )
            return {
                "stop": "max_products",
                "page_n": _page_n,
                "enqueued_on_this_page": enqueued,
            }
        await redis.enqueue_job("ingest_product_job", product_url, _queue_name=QUEUE_NAME)
        enqueued += 1

    new_total = _processed + enqueued
    next_url = listing.next_page_url
    next_enqueued = False

    if next_url and _page_n < max_pages:
        if max_products is None or new_total < max_products:
            await redis.enqueue_job(
                "crawl_listing_job",
                next_url,
                max_pages,
                max_products,
                _queue_name=QUEUE_NAME,
                _page_n=_page_n + 1,
                _processed=new_total,
            )
            next_enqueued = True

    log.info(
        "crawl_page_done",
        start_url=start_url,
        page_n=_page_n,
        enqueued=enqueued,
        next_enqueued=next_enqueued,
    )
    return {
        "page_n": _page_n,
        "enqueued": enqueued,
        "next_enqueued": next_enqueued,
    }


# ---------------------------------------------------------------------------


async def download_media_job(ctx: dict[str, Any], asset_id: str) -> dict[str, Any]:
    """Fetch → validate → hash → upsert MediaBlob → upload to S3 → link MediaAsset.

    Outcomes (returned as `status`) :
      - "downloaded"  : new blob, uploaded, asset linked, status=OK
      - "dedup"       : blob already existed, no upload, asset linked, status=OK
      - "already_ok"  : asset was already linked to a blob (no-op)
      - "not_pending" : asset is FAILED/QUARANTINED — refuse to re-process
      - "fetch_failed": network/HTTP error → asset status=FAILED
      - "invalid"     : payload not a valid image / too big → status=QUARANTINED
      - "not_found"   : asset_id unknown
    """

    log = get_logger("job.download_media")
    settings = get_settings()

    try:
        uuid_asset_id = UUID(asset_id)
    except ValueError:
        log.warning("download_media_bad_id", asset_id=asset_id)
        return {"asset_id": asset_id, "status": "bad_id"}

    fetcher = ctx["fetcher"]
    storage = ctx["storage"]
    session_factory = ctx["session_factory"]

    # Step 1: read the MediaAsset (its original_url + current status)
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        asset = await uow.media_assets.get_by_id(uuid_asset_id)

    if asset is None:
        log.warning("download_media_not_found", asset_id=asset_id)
        return {"asset_id": asset_id, "status": "not_found"}

    if asset.status is MediaStatus.OK and asset.media_blob_hash is not None:
        return {"asset_id": asset_id, "status": "already_ok"}

    if asset.status in (MediaStatus.FAILED, MediaStatus.QUARANTINED):
        return {"asset_id": asset_id, "status": "not_pending"}

    # Step 2: fetch the bytes via the shared TieredFetcher
    try:
        response = await fetcher.fetch(FetchRequest(url=asset.original_url, timeout_s=30))
    except FetchError as exc:
        log.warning(
            "download_media_fetch_failed",
            asset_id=asset_id,
            url=asset.original_url,
            error=str(exc),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            await uow.media_assets.mark_status(uuid_asset_id, status=MediaStatus.FAILED)
            await uow.commit()
        return {"asset_id": asset_id, "status": "fetch_failed"}

    # Step 3: Pillow validation + WebP normalisation
    try:
        normalized = validate_and_normalize(
            response.body,
            max_bytes=settings.media.max_bytes,
            webp_quality=settings.media.webp_quality,
        )
    except ImageValidationError as exc:
        log.warning(
            "download_media_invalid",
            asset_id=asset_id,
            url=asset.original_url,
            reason=str(exc),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            await uow.media_assets.mark_status(uuid_asset_id, status=MediaStatus.QUARANTINED)
            await uow.commit()
        return {"asset_id": asset_id, "status": "invalid"}

    # Step 4: hash + upsert MediaBlob (idempotent on content_hash)
    content_hash = blake3_hex(normalized.data)
    now = datetime.now(tz=UTC)
    new_blob = MediaBlob(
        content_hash=content_hash,
        storage_key=f"{content_hash[:2]}/{content_hash}.{normalized.ext}",
        mime_type=normalized.mime_type,
        byte_size=len(normalized.data),
        width_px=normalized.width,
        height_px=normalized.height,
        first_seen_at=now,
    )
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        blob, inserted = await uow.media_blobs.add(new_blob)
        await uow.commit()

    # Step 5: upload to S3 ONLY when we inserted a new blob (skip on dedup).
    #         Even if `inserted=True` the storage might already have the
    #         object (e.g. PG was wiped but the bucket wasn't) — `put` is
    #         idempotent on the same key.
    if inserted:
        try:
            await storage.put(
                content_hash=blob.content_hash,
                data=normalized.data,
                ext=normalized.ext,
                mime_type=blob.mime_type,
            )
            outcome = "downloaded"
        except StorageError as exc:
            log.error(
                "download_media_storage_failed",
                asset_id=asset_id,
                content_hash=content_hash,
                error=str(exc),
            )
            async with SqlAlchemyUnitOfWork(session_factory) as uow:
                await uow.media_assets.mark_status(uuid_asset_id, status=MediaStatus.FAILED)
                await uow.commit()
            return {"asset_id": asset_id, "status": "storage_failed"}
    else:
        outcome = "dedup"

    # Step 6: link the asset to the blob and flip to OK
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await uow.media_assets.mark_status(
            uuid_asset_id,
            status=MediaStatus.OK,
            media_blob_hash=blob.content_hash,
        )
        await uow.commit()

    log.info(
        "download_media_done",
        asset_id=asset_id,
        outcome=outcome,
        content_hash=content_hash,
        bytes=len(normalized.data),
        dims=f"{normalized.width}x{normalized.height}",
    )
    return {
        "asset_id": asset_id,
        "status": outcome,
        "content_hash": content_hash,
    }


# ---------------------------------------------------------------------------
# Customs jobs
# ---------------------------------------------------------------------------


async def refresh_customs_source_job(ctx: dict[str, Any], source_code: str) -> dict[str, Any]:
    """Scan a customs source's index for new publications.

    Each newly discovered publication is persisted (status=DISCOVERED) and
    enqueued for ingestion via `ingest_customs_publication_job`.
    """

    log = get_logger("job.refresh_customs_source")
    use_case = RefreshCustomsSourceUseCase(fetcher=ctx["fetcher"])

    async with SqlAlchemyUnitOfWork(ctx["session_factory"]) as uow:
        report = await use_case.execute(source_code=source_code, uow=uow)

    redis = ctx.get("redis")
    enqueued = 0
    if redis is not None and report.new_publication_ids:
        for pid in report.new_publication_ids:
            await redis.enqueue_job("ingest_customs_publication_job", pid, _queue_name=QUEUE_NAME)
            enqueued += 1

    payload = {
        "source_code": source_code,
        "total_seen": report.total_seen,
        "new_publications": report.new_publications,
        "ingest_jobs_enqueued": enqueued,
        "error": report.error,
    }
    log.info("refresh_customs_source_done", **payload)
    return payload


async def refresh_customs_fr_job(ctx: dict[str, Any]) -> dict[str, Any]:
    """Cron wrapper: refresh the French Légifrance JORF source."""
    return await refresh_customs_source_job(ctx, "fr-legifrance-jorf")


async def refresh_customs_ch_job(ctx: dict[str, Any]) -> dict[str, Any]:
    """Cron wrapper: refresh the Swiss OFDF source."""
    return await refresh_customs_source_job(ctx, "ch-ofdf")


async def ingest_customs_publication_job(
    ctx: dict[str, Any], publication_id: str
) -> dict[str, Any]:
    """Fetch one regulator document and upsert its price entries."""

    log = get_logger("job.ingest_customs_publication")
    try:
        uuid_pub_id = UUID(publication_id)
    except ValueError:
        log.warning("ingest_customs_bad_id", publication_id=publication_id)
        return {"publication_id": publication_id, "status": "bad_id"}

    use_case = IngestCustomsPublicationUseCase(fetcher=ctx["fetcher"])
    async with SqlAlchemyUnitOfWork(ctx["session_factory"]) as uow:
        report = await use_case.execute(publication_id=uuid_pub_id, uow=uow)

    payload = {
        "publication_id": report.publication_id,
        "status": report.status,
        "entries_inserted": report.entries_inserted,
        "error": report.error,
    }
    log.info("ingest_customs_publication_done", **payload)
    return payload


# ---------------------------------------------------------------------------
# Matching jobs
# ---------------------------------------------------------------------------


async def compute_embeddings_job(
    ctx: dict[str, Any],
    target: str = "all",
    batch_size: int = 256,
    max_batches: int | None = None,
) -> dict[str, Any]:
    """Encode + persist embeddings for cigars / customs entries that lack one."""

    log = get_logger("job.compute_embeddings")
    if target not in ("cigar", "customs", "all"):
        return {"status": "bad_target", "target": target}

    use_case = BuildEmbeddingsUseCase(embedder=ctx["embedder"])
    async with SqlAlchemyUnitOfWork(ctx["session_factory"]) as uow:
        report = await use_case.execute(
            uow=uow,
            target=target,  # type: ignore[arg-type]
            batch_size=batch_size,
            max_batches=max_batches,
        )

    payload = {
        "target": report.target,
        "encoded": report.encoded,
        "batches": report.batches,
    }
    log.info("compute_embeddings_done", **payload)
    return payload


async def match_cigar_job(ctx: dict[str, Any], cigar_id: str) -> dict[str, Any]:
    """Score one cigar against the customs catalog and upsert its matches."""

    log = get_logger("job.match_cigar")
    try:
        uuid_id = UUID(cigar_id)
    except ValueError:
        return {"cigar_id": cigar_id, "status": "bad_id"}

    use_case = MatchCigarToCustomsUseCase()
    async with SqlAlchemyUnitOfWork(ctx["session_factory"]) as uow:
        report = await use_case.execute(cigar_id=uuid_id, uow=uow)

    payload = {
        "cigar_id": report.cigar_id,
        "candidates_seen": report.candidates_seen,
        "matches_upserted": report.matches_upserted,
        "error": report.error,
        **report.counts_by_status,
    }
    log.info("match_cigar_done", **payload)
    return payload


async def match_all_cigars_job(ctx: dict[str, Any], limit: int | None = None) -> dict[str, Any]:
    """Fan-out: enqueue one match_cigar_job per cigar that has an embedding."""

    log = get_logger("job.match_all_cigars")
    redis = ctx["redis"]
    async with SqlAlchemyUnitOfWork(ctx["session_factory"]) as uow:
        ids = await uow.matching.list_cigar_ids_with_embedding(limit=limit)

    enqueued = 0
    for cigar_id in ids:
        await redis.enqueue_job("match_cigar_job", str(cigar_id), _queue_name=QUEUE_NAME)
        enqueued += 1

    log.info("match_all_cigars_done", enqueued=enqueued)
    return {"enqueued": enqueued}
