# Architecture

Cigarspace is a layered DDD application. The repository follows a strict
4-folder layout under `src/`:

```
src/
  domain/          Pure Pydantic entities, enums, value objects.
  application/     Ports (Protocols) + use cases. No I/O.
  infrastructure/ Concrete adapters: PG repositories, S3 storage, HTTP fetchers,
                  parsers, customs adapters, embedder, worker, etc.
  presentation/    Entry points: CLI (typer) and HTTP API (FastAPI).
```

External I/O never bleeds into `domain/` or `application/`. The
`application/ports/` Protocols are the contract; `infrastructure/`
implements them; `presentation/` wires them together.

## High-level system

```mermaid
flowchart LR
  subgraph external [External world]
    Merchant[Cigar merchants<br/>mistercigar.com / cigarpassion.ch / …]
    DGDDI[FR customs<br/>douane.gouv.fr opendata]
    DILA[Légifrance / PISTE]
  end

  subgraph cigarspace [Cigarspace]
    direction TB
    CLI[CLI · typer]
    API[Public API · FastAPI]
    Worker[Worker · arq]
    DB[(PostgreSQL<br/>+ pgvector + pg_trgm)]
    Cache[(Redis)]
    Storage[(S3 / SeaweedFS)]
    Web[Admin Web · React]
  end

  Merchant --> Worker
  DGDDI --> Worker
  DILA --> Worker

  CLI --> Worker
  CLI --> DB

  Worker --> DB
  Worker --> Cache
  Worker --> Storage

  API --> DB
  API --> Cache
  API --> Storage
  Web --> API
```

## Layered structure

```mermaid
flowchart TB
  subgraph presentation [presentation/]
    CLI_layer[CLI · cigarspace command]
    API_layer[HTTP API · routers, middleware, security]
    Web_layer[Web admin · React SPA · web/]
  end

  subgraph application [application/]
    UseCases[Use cases<br/>IngestProductUrlUseCase<br/>RefreshCustomsSourceUseCase<br/>IngestCustomsPublicationUseCase<br/>BuildEmbeddingsUseCase<br/>MatchCigarToCustomsUseCase<br/>HybridSearchUseCase]
    Ports[Ports<br/>IFetcher · IParser · ICigarRepository<br/>ICustoms*Repository · IMediaStorage<br/>IEmbedder · IMatchingRepository · IUnitOfWork]
  end

  subgraph domain [domain/]
    Entities[Pydantic entities<br/>Brand · CigarLine · Cigar<br/>CigarPackage · BlendComponent<br/>CustomsSource · CustomsPublication<br/>CustomsPriceEntry · CigarCustomsMatch<br/>MediaAsset · MediaBlob · ApiUser]
    Enums[StrEnums<br/>FormatCategory · Intensity · MatchMethod<br/>CustomsMatchStatus · CustomsPublicationStatus]
  end

  subgraph infrastructure [infrastructure/]
    Fetchers[TieredFetcher<br/>L0 httpx · L1 curl_cffi<br/>L2 ProtonVPN · L3 Tor · L4 patchright]
    Parsers[ParserRegistry<br/>MistercigarParser · CigarpassionParser]
    Customs[CustomsAdapterRegistry<br/>Discovery: legifrance-jorf / legifrance-dila / douane-opendata<br/>Extractors: legifrance-html / legifrance-dila-json / douane-ods / pdf-table]
    Persistence[PostgreSQL<br/>SQLAlchemy 2.0 async<br/>UoW + repositories]
    Matching[MatchingPipeline<br/>SentenceTransformer embedder<br/>rapidfuzz · normalization · scorer]
    Media[Media pipeline<br/>Pillow + BLAKE3 + WebP<br/>SeaweedFS S3 storage]
    Workers[arq workers<br/>+ Redis queues + crons]
  end

  CLI_layer --> UseCases
  API_layer --> UseCases
  Web_layer --> API_layer

  UseCases --> Ports
  UseCases --> Entities

  Ports -.implemented by.-> Fetchers
  Ports -.implemented by.-> Parsers
  Ports -.implemented by.-> Customs
  Ports -.implemented by.-> Persistence
  Ports -.implemented by.-> Matching
  Ports -.implemented by.-> Media
  Ports -.implemented by.-> Workers
```

## Request flow — public read

A `GET /api/v1/cigars/{slug}` traverses:

1. `presentation/api/routers/cigars.py` — extracts the slug, calls
   `dependencies.get_uow()` to obtain a transactional UoW.
2. `application/ports/cigar_repository.py::ICigarRepository.get_by_slug` —
   the contract.
3. `infrastructure/persistence/repositories/cigar.py::PgCigarRepository` —
   issues an async SQLAlchemy query.
4. `infrastructure/persistence/mappers.py` — translates the ORM row into
   the `domain/entities/cigar.py::Cigar` Pydantic entity.
5. The router serialises the entity into `presentation/api/schemas/cigar.py`
   (with HATEOAS `_links`) and returns it.

Every layer talks to the next via Protocols / Pydantic, never with
concrete adapters.

## Background-job flow

Triggered by a CLI command, an API admin endpoint, or a cron in the
worker definition:

1. `presentation/cli/__main__.py` or `routers/match_jobs.py` enqueues
   a job into the Redis queue `cigarspace:default` via `arq`.
2. `infrastructure/workers/worker.py` worker process picks the job,
   loads the appropriate use case, runs it inside a UoW.
3. Side effects (e.g. embeddings written, media downloaded, customs
   parsed) commit transactionally.
4. The CLI / API client polls `GET /api/v1/jobs/{id}` (admin) to read
   status — backed by arq's job metadata in Redis.

## Persistence model

See [`data-model.md`](./data-model.md) for the full ER diagram and
table-by-table description.

## Matching pipeline

See [`matching-pipeline.md`](./matching-pipeline.md) for the four signals
(`exact`, `fuzzy`, `vector`, `pack_compat`), the Reciprocal Rank Fusion
formula and the workflow that protects `HUMAN_*` verdicts across
re-runs.

## Customs sources

See [`customs-sources.md`](./customs-sources.md) for the adapter
registry, the source-of-truth for each jurisdiction, and the steps to
add a new country.

## Deployment

See [`deployment/docker.md`](./deployment/docker.md) and
[`deployment/production.md`](./deployment/production.md).
