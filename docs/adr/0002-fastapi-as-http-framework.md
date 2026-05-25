# 2. FastAPI as the HTTP framework

Date: 2026-05-25

## Status

Accepted

## Context

The platform needed a public HTTP layer over the existing async Python
stack (asyncpg, SQLAlchemy async, arq workers). Hard constraints:

- Native `async` (we run hundreds of concurrent HTTP fetches alongside
  DB I/O).
- Pydantic v2 — already the data layer's source of truth across the
  domain, persistence mappers and DTOs.
- First-class OpenAPI generation — the API surface is part of the
  public contract.
- Modest cold-start time (we run on small VMs and in CI).
- Mature ecosystem for auth, rate-limiting, middleware, security.

## Decision

We adopt **FastAPI ≥ 0.110** running on **Uvicorn**.

- The whole presentation layer (`src/presentation/api/`) is built on
  FastAPI routers + Pydantic v2 request/response models.
- OpenAPI 3.1 is the single source of truth for the API contract.
- We use `slowapi` for rate-limiting and `python-jose`/`pyjwt` +
  `argon2-cffi` for auth.

Candidates considered:

| Option        | Why we did not pick it                                           |
| ------------- | ---------------------------------------------------------------- |
| **Starlette** alone | We would have re-implemented half of FastAPI (DI, OpenAPI). |
| **Litestar**  | Faster on micro-benchmarks but smaller ecosystem; harder to find contributors. |
| **Flask + extensions** | Sync-first, OpenAPI is bolted on, slower in our workload. |
| **Django + DRF** | Too opinionated, ORM duplicates SQLAlchemy; not async-native. |

## Consequences

- Most contributors will arrive with prior FastAPI exposure — onboarding
  is cheaper.
- Pydantic v2's strict typing flows end-to-end from DB to JSON.
- The dependency injection system (`Depends(...)`) drives the UoW + auth
  flow cleanly.
- We accept being on a fast-moving framework: minor releases sometimes
  bring breaking changes — pinned in `pyproject.toml` to a major-stable
  range.
