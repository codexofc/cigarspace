# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Cigars CLI entrypoint."""

from __future__ import annotations

import asyncio
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

import typer
from rich.console import Console
from rich.table import Table

from application.use_cases.crawl_listing import CrawlListingUseCase
from application.use_cases.ingest_product import IngestProductUrlUseCase
from infrastructure.config import get_settings
from infrastructure.fetcher.curl_cffi_fetcher import DEFAULT_IMPERSONATE_POOL, CurlCffiFetcher
from infrastructure.observability.logging import configure_logging, get_logger
from infrastructure.parsers import (
    UnknownDomainError,
    listing_parser_for_url,
    product_parser_for_url,
)
from infrastructure.persistence.session import build_engine, build_session_factory
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

app = typer.Typer(
    name="cigars",
    help="Industrial scraping & ingestion pipeline for the global cigar market.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


@app.callback()
def _bootstrap() -> None:
    configure_logging()


@app.command()
def version() -> None:
    """Print application version."""

    try:
        ver = pkg_version("cigars")
    except PackageNotFoundError:
        ver = "0.0.0+unknown"
    console.print(f"[bold cyan]cigars[/] {ver}")


@app.command()
def info() -> None:
    """Print current configuration summary (no secrets)."""

    settings = get_settings()

    table = Table(title="cigars — configuration", show_header=True, header_style="bold")
    table.add_column("Section", style="cyan")
    table.add_column("Key")
    table.add_column("Value")

    table.add_row("app", "env", settings.app.env)
    table.add_row("postgres", "host", settings.postgres.host)
    table.add_row("postgres", "port", str(settings.postgres.port))
    table.add_row("postgres", "db", settings.postgres.db)
    table.add_row("postgres", "user", settings.postgres.user)
    table.add_row("redis", "host", settings.redis.host)
    table.add_row("redis", "port", str(settings.redis.port))
    table.add_row("redis", "db", str(settings.redis.db))
    table.add_row("log", "level", settings.log.level)
    table.add_row("log", "format", settings.log.format)

    console.print(table)


@app.command()
def healthcheck() -> None:
    """Probe Postgres & Redis connectivity from the current environment."""

    asyncio.run(_run_healthcheck())


async def _run_healthcheck() -> None:
    log = get_logger("healthcheck")
    settings = get_settings()
    failures = 0

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(settings.postgres.dsn, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar_one()
        if value == 1:
            console.print("[green]:heavy_check_mark:[/] PostgreSQL OK")
            log.info("postgres_ok", host=settings.postgres.host, port=settings.postgres.port)
        else:
            console.print(f"[red]:x:[/] PostgreSQL returned unexpected value: {value!r}")
            failures += 1
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]:x:[/] PostgreSQL: {exc}")
        log.error("postgres_fail", error=str(exc))
        failures += 1
    finally:
        await engine.dispose()

    import redis.asyncio as redis_async

    client = redis_async.from_url(settings.redis.dsn)
    try:
        pong = await client.ping()
        if pong:
            console.print("[green]:heavy_check_mark:[/] Redis OK")
            log.info("redis_ok", host=settings.redis.host, port=settings.redis.port)
        else:
            console.print("[red]:x:[/] Redis ping returned falsy")
            failures += 1
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]:x:[/] Redis: {exc}")
        log.error("redis_fail", error=str(exc))
        failures += 1
    finally:
        await client.aclose()

    if failures:
        raise typer.Exit(code=1)


@app.command("ingest-url")
def ingest_url_cmd(
    url: str = typer.Argument(..., help="Product detail URL (auto-detects merchant)"),
) -> None:
    """Fetch one product URL → upsert Brand / CigarLine / Cigar in the DB."""

    asyncio.run(_run_ingest_url(url))


async def _run_ingest_url(url: str) -> None:
    log = get_logger("cli.ingest_url")
    engine = build_engine()
    factory = build_session_factory(engine)
    fetcher = CurlCffiFetcher(impersonate_pool=DEFAULT_IMPERSONATE_POOL)
    try:
        try:
            parser = product_parser_for_url(url)
        except UnknownDomainError as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(code=2)
        use_case = IngestProductUrlUseCase(fetcher=fetcher, parser=parser)
        async with SqlAlchemyUnitOfWork(factory) as uow:
            result = await use_case.execute(url=url, uow=uow)

        c = result.cigar
        outcome = result.outcome.value
        console.print(
            f"[bold]{outcome.upper()}[/]  [cyan]{c.slug}[/]  "
            f"[white]{c.full_name}[/]  vitola=[magenta]{c.vitola_name}[/]  "
            f"L={c.length_mm}mm  cepo={c.ring_gauge}  strength={c.strength}"
        )
        log.info(
            "ingest_done",
            url=url,
            outcome=outcome,
            cigar_id=str(c.id),
            slug=c.slug,
        )
    finally:
        await fetcher.aclose()
        await engine.dispose()


@app.command("crawl-listing")
def crawl_listing_cmd(
    url: str = typer.Argument(..., help="Listing page URL (category)"),
    max_pages: int = typer.Option(3, "--max-pages", help="Max pagination pages to walk"),
    max_products: int = typer.Option(50, "--max-products", help="Hard cap on products processed"),
) -> None:
    """Walk a category listing on mistercigar.com and ingest every product."""

    asyncio.run(_run_crawl_listing(url, max_pages, max_products))


async def _run_crawl_listing(url: str, max_pages: int, max_products: int) -> None:
    engine = build_engine()
    factory = build_session_factory(engine)
    fetcher = CurlCffiFetcher(impersonate_pool=DEFAULT_IMPERSONATE_POOL)
    try:
        try:
            listing = listing_parser_for_url(url)
            product = product_parser_for_url(url)
        except UnknownDomainError as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(code=2)
        use_case = CrawlListingUseCase(
            fetcher=fetcher,
            listing_parser=listing,
            product_parser=product,
            session_factory=factory,
        )
        report = await use_case.execute(
            start_url=url, max_pages=max_pages, max_products=max_products
        )

        table = Table(title="Crawl report", show_header=True, header_style="bold")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_row("Pages visited", str(report.pages_visited))
        table.add_row("Products seen", str(report.products_seen))
        table.add_row("Created", f"[green]{report.created}[/]")
        table.add_row("Already present", str(report.already_present))
        table.add_row("Failed", f"[red]{report.failed}[/]" if report.failed else "0")
        console.print(table)

        if report.errors:
            console.print("\n[bold red]Errors:[/]")
            for url, msg in report.errors[:10]:
                console.print(f"  [red]✗[/] {url}: {msg}")
            if len(report.errors) > 10:
                console.print(f"  ... +{len(report.errors) - 10} more")
    finally:
        await fetcher.aclose()
        await engine.dispose()


# ---------------------------------------------------------------------------
# Worker (arq)
# ---------------------------------------------------------------------------


@app.command("worker")
def worker_cmd() -> None:
    """Run an arq worker in the foreground (Ctrl-C to stop)."""

    from arq.worker import run_worker

    from infrastructure.workers.worker import WorkerSettings

    run_worker(WorkerSettings)  # type: ignore[arg-type]


@app.command("enqueue-ingest")
def enqueue_ingest_cmd(
    url: str = typer.Argument(..., help="Product detail URL"),
) -> None:
    """Push an ingest_product_job into the worker queue (non-blocking)."""

    asyncio.run(_enqueue("ingest_product_job", url))


@app.command("enqueue-crawl")
def enqueue_crawl_cmd(
    url: str = typer.Argument(..., help="Category listing URL"),
    max_pages: int = typer.Option(5, "--max-pages"),
    max_products: int = typer.Option(50, "--max-products"),
) -> None:
    """Push a crawl_listing_job into the worker queue (non-blocking)."""

    asyncio.run(_enqueue("crawl_listing_job", url, max_pages, max_products))


async def _enqueue(job_name: str, *args: object) -> None:
    from arq.connections import create_pool

    from infrastructure.workers.queues import QUEUE_NAME
    from infrastructure.workers.worker import arq_redis_settings

    pool = await create_pool(arq_redis_settings())
    try:
        job = await pool.enqueue_job(job_name, *args, _queue_name=QUEUE_NAME)
        job_id = getattr(job, "job_id", "?")
        console.print(
            f"[green]Enqueued[/] [cyan]{job_name}[/] on [magenta]{QUEUE_NAME}[/]  job_id={job_id}"
        )
    finally:
        await pool.aclose()


# ---------------------------------------------------------------------------
# Customs
# ---------------------------------------------------------------------------


@app.command("customs-seed")
def customs_seed_cmd(
    yaml_path: str = typer.Option(
        "config/customs_sources.yaml",
        "--file",
        "-f",
        help="YAML seed file path (default: config/customs_sources.yaml)",
    ),
) -> None:
    """Upsert customs sources from the seed YAML into the customs_source table."""

    asyncio.run(_run_customs_seed(yaml_path))


async def _run_customs_seed(yaml_path: str) -> None:
    from pathlib import Path

    from application.use_cases.seed_customs_sources import SeedCustomsSourcesUseCase
    from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    engine = build_engine()
    factory = build_session_factory(engine)
    try:
        use_case = SeedCustomsSourcesUseCase()
        async with SqlAlchemyUnitOfWork(factory) as uow:
            report = await use_case.execute(yaml_path=Path(yaml_path), uow=uow)
        console.print(
            f"[green]Seeded[/] {report.upserted} source(s): [cyan]{', '.join(report.codes)}[/]"
        )
    finally:
        await engine.dispose()


@app.command("customs-status")
def customs_status_cmd() -> None:
    """Display all customs sources with their runtime state."""

    asyncio.run(_run_customs_status())


async def _run_customs_status() -> None:
    from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

    engine = build_engine()
    factory = build_session_factory(engine)
    try:
        async with SqlAlchemyUnitOfWork(factory) as uow:
            sources = await uow.customs_sources.list_all()

        table = Table(title="Customs sources", show_header=True, header_style="bold")
        table.add_column("Code", style="cyan")
        table.add_column("Country")
        table.add_column("Active", justify="center")
        table.add_column("Currency")
        table.add_column("Last checked")
        table.add_column("Last pub ref")
        table.add_column("Fails", justify="right")

        for s in sources:
            table.add_row(
                s.code,
                s.country_code,
                "[green]✓[/]" if s.is_active else "[dim]—[/]",
                s.default_currency_code,
                s.last_checked_at.isoformat(timespec="minutes") if s.last_checked_at else "—",
                s.last_publication_seen_ref or "—",
                str(s.consecutive_failures),
            )
        console.print(table)
    finally:
        await engine.dispose()


@app.command("customs-discover")
def customs_discover_cmd(
    source_code: str = typer.Option(..., "--source", help="Source code (e.g. fr-legifrance-jorf)"),
) -> None:
    """Enqueue a refresh_customs_source_job for the given source code."""

    asyncio.run(_enqueue("refresh_customs_source_job", source_code))


@app.command("customs-ingest")
def customs_ingest_cmd(
    publication_id: str = typer.Option(
        ..., "--publication-id", help="UUID of the customs_publication to ingest"
    ),
) -> None:
    """Enqueue an ingest_customs_publication_job for a specific publication."""

    asyncio.run(_enqueue("ingest_customs_publication_job", publication_id))


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


@app.command("embeddings-build")
def embeddings_build_cmd(
    target: str = typer.Option("all", "--target", help="cigar | customs | all"),
    batch_size: int = typer.Option(256, "--batch-size"),
) -> None:
    """Enqueue compute_embeddings_job — encode rows that lack an embedding."""

    asyncio.run(_enqueue("compute_embeddings_job", target, batch_size))


@app.command("match-cigar")
def match_cigar_cmd(
    cigar_id: str = typer.Option(..., "--cigar-id", help="UUID of the cigar"),
) -> None:
    """Enqueue match_cigar_job for one cigar."""

    asyncio.run(_enqueue("match_cigar_job", cigar_id))


@app.command("match-all")
def match_all_cmd(
    limit: int | None = typer.Option(None, "--limit", help="Cap on cigars enqueued"),
) -> None:
    """Fan-out: enqueue one match_cigar_job per cigar with an embedding."""

    asyncio.run(_enqueue("match_all_cigars_job", limit))


@app.command("match-review")
def match_review_cmd(
    limit: int = typer.Option(20, "--limit"),
) -> None:
    """Show the top of the PENDING_REVIEW queue (the matches needing humans)."""

    asyncio.run(_show_review_queue(limit))


async def _show_review_queue(limit: int) -> None:
    from rich.table import Table
    from sqlalchemy import select

    from domain.enums import CustomsMatchStatus
    from infrastructure.persistence.models import (
        CigarCustomsMatchModel,
        CigarModel,
        CustomsPriceEntryModel,
    )
    from infrastructure.persistence.session import build_engine, build_session_factory

    engine = build_engine()
    factory = build_session_factory(engine)
    try:
        async with factory() as session:
            stmt = (
                select(
                    CigarCustomsMatchModel.id,
                    CigarCustomsMatchModel.score,
                    CigarCustomsMatchModel.signals,
                    CigarCustomsMatchModel.pack_size_bucket,
                    CigarModel.full_name,
                    CustomsPriceEntryModel.raw_brand_label,
                    CustomsPriceEntryModel.raw_product_label,
                    CustomsPriceEntryModel.unit_price,
                )
                .join(CigarModel, CigarModel.id == CigarCustomsMatchModel.cigar_id)
                .join(
                    CustomsPriceEntryModel,
                    CustomsPriceEntryModel.id == CigarCustomsMatchModel.customs_entry_id,
                )
                .where(CigarCustomsMatchModel.status == CustomsMatchStatus.PENDING_REVIEW)
                .order_by(CigarCustomsMatchModel.score.desc())
                .limit(limit)
            )
            rows = (await session.execute(stmt)).all()

        table = Table(title=f"Pending review queue (top {limit})")
        table.add_column("score", justify="right")
        table.add_column("pack")
        table.add_column("cigar")
        table.add_column("customs (brand / product)")
        table.add_column("€", justify="right")
        for row in rows:
            table.add_row(
                f"{row.score:.3f}",
                str(row.pack_size_bucket or "—"),
                row.full_name[:50],
                f"{row.raw_brand_label} / {row.raw_product_label[:50]}",
                f"{row.unit_price}",
            )
        console.print(table)
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# API users (public HTTP API authentication)
# ---------------------------------------------------------------------------


users_app = typer.Typer(
    name="users",
    help="Manage API users (create, list).",
    no_args_is_help=True,
)
app.add_typer(users_app, name="users")


@users_app.command("create")
def users_create_cmd(
    email: str = typer.Option(..., "--email", help="User email (case-insensitive)."),
    password: str = typer.Option(
        ..., "--password", help="Plain password — will be hashed (argon2id)."
    ),
    full_name: str | None = typer.Option(None, "--full-name"),
    admin: bool = typer.Option(False, "--admin", help="Grant admin privileges."),
) -> None:
    """Create a new API user."""
    asyncio.run(_run_users_create(email, password, full_name, admin))


async def _run_users_create(email: str, password: str, full_name: str | None, admin: bool) -> None:
    from domain.entities.api_user import ApiUser
    from presentation.api.security.password import hash_password

    engine = build_engine()
    factory = build_session_factory(engine)
    try:
        async with SqlAlchemyUnitOfWork(factory) as uow:
            if await uow.api_users.get_by_email(email):
                console.print(f"[red]User {email} already exists[/]")
                raise typer.Exit(code=1)
            user = await uow.api_users.add(
                ApiUser(
                    email=email,
                    full_name=full_name,
                    password_hash=hash_password(password),
                    is_admin=admin,
                )
            )
            await uow.commit()
        console.print(
            f"[green]Created user[/] [cyan]{user.email}[/] "
            f"(id=[magenta]{user.id}[/], admin=[yellow]{admin}[/])"
        )
    finally:
        await engine.dispose()


@users_app.command("list")
def users_list_cmd() -> None:
    """List API users."""
    asyncio.run(_run_users_list())


async def _run_users_list() -> None:
    engine = build_engine()
    factory = build_session_factory(engine)
    try:
        async with SqlAlchemyUnitOfWork(factory) as uow:
            users = list(await uow.api_users.list_all(limit=1000))
            total = await uow.api_users.count()

        table = Table(title=f"API users ({total} total)")
        table.add_column("email")
        table.add_column("full_name")
        table.add_column("admin", justify="center")
        table.add_column("active", justify="center")
        table.add_column("last_login")
        for user in users:
            table.add_row(
                user.email,
                user.full_name or "—",
                "✓" if user.is_admin else "—",
                "✓" if user.is_active else "—",
                user.last_login_at.isoformat() if user.last_login_at else "—",
            )
        console.print(table)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    app()
