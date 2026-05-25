# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""arq worker setup — startup/shutdown lifecycle + WorkerSettings.

The worker process holds shared instances (fetcher, DB engine, session
factory) in `ctx` so jobs reuse them across invocations:
- CurlCffiFetcher keeps its HTTP connection pool warm
- AsyncEngine pools PG connections across jobs
- arq itself provides ctx['redis'] (the redis pool) so jobs can enqueue
  further jobs.

Launch:
    uv run arq infrastructure.workers.worker.WorkerSettings
or via the CLI:
    cigars worker
"""

from __future__ import annotations

from typing import Any

from arq import cron
from arq.connections import RedisSettings as ArqRedisSettings

# Importing infrastructure.customs populates the CustomsAdapterRegistry
# (discovery + extractor adapters) before any customs job runs.
import infrastructure.customs  # noqa: F401
from infrastructure.config import get_settings
from infrastructure.fetcher.curl_cffi_fetcher import (
    CurlCffiFetcher,
    DEFAULT_IMPERSONATE_POOL,
)
from infrastructure.media.seaweed_storage import SeaweedS3Storage
from infrastructure.observability.logging import configure_logging, get_logger
from infrastructure.persistence.session import build_engine, build_session_factory
from infrastructure.matching.sentence_transformer_embedder import (
    SentenceTransformerEmbedder,
)
from infrastructure.workers.jobs import (
    compute_embeddings_job,
    crawl_listing_job,
    download_media_job,
    ingest_customs_publication_job,
    ingest_product_job,
    match_all_cigars_job,
    match_cigar_job,
    refresh_customs_ch_job,
    refresh_customs_fr_job,
    refresh_customs_source_job,
)
from infrastructure.workers.queues import QUEUE_NAME


def arq_redis_settings() -> ArqRedisSettings:
    s = get_settings()
    return ArqRedisSettings(host=s.redis.host, port=s.redis.port, database=s.redis.db)


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging()
    log = get_logger("worker.startup")
    settings = get_settings()
    fetcher = CurlCffiFetcher(impersonate_pool=DEFAULT_IMPERSONATE_POOL)
    engine = build_engine()
    session_factory = build_session_factory(engine)
    storage = SeaweedS3Storage(
        endpoint_url=settings.s3.endpoint_url,
        bucket=settings.s3.bucket,
        access_key_id=settings.s3.access_key_id,
        secret_access_key=settings.s3.secret_access_key,
        region=settings.s3.region,
    )
    await storage.ensure_bucket()
    ctx["fetcher"] = fetcher
    ctx["engine"] = engine
    ctx["session_factory"] = session_factory
    ctx["storage"] = storage
    # Embedder is shared across jobs; lazy-loads its model on the first
    # encode() so the worker startup itself stays cheap.
    ctx["embedder"] = SentenceTransformerEmbedder()
    log.info(
        "worker_started",
        impersonate_pool=list(DEFAULT_IMPERSONATE_POOL),
        s3_bucket=settings.s3.bucket,
        s3_endpoint=settings.s3.endpoint_url,
        max_jobs=ctx.get("max_jobs"),
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    log = get_logger("worker.shutdown")
    fetcher = ctx.get("fetcher")
    storage = ctx.get("storage")
    engine = ctx.get("engine")
    if fetcher is not None:
        await fetcher.aclose()
    if storage is not None:
        await storage.aclose()
    if engine is not None:
        await engine.dispose()
    log.info("worker_stopped")


class WorkerSettings:
    """arq entrypoint. Discovered by `arq` CLI via dotted-path import."""

    redis_settings = arq_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    functions = [
        ingest_product_job,
        crawl_listing_job,
        download_media_job,
        refresh_customs_source_job,
        refresh_customs_fr_job,
        refresh_customs_ch_job,
        ingest_customs_publication_job,
        compute_embeddings_job,
        match_cigar_job,
        match_all_cigars_job,
    ]
    max_jobs = 4  # concurrent jobs per worker process
    job_timeout = 600  # seconds — embeddings batch can take a while
    keep_result = 3600  # keep job results 1h for inspection
    queue_name = QUEUE_NAME

    # Periodic customs refresh.
    # FR (Légifrance): daily at 06:00 — arrêtés tombent 3-6×/an.
    # CH (OFDF): weekly Monday 07:00 — fréquence inconnue, on est conservateur.
    cron_jobs = [
        cron(refresh_customs_fr_job, name="customs_refresh_fr", hour={6}, minute={0}),
        cron(
            refresh_customs_ch_job,
            name="customs_refresh_ch",
            weekday="mon",
            hour={7},
            minute={0},
        ),
    ]
