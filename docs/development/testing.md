# Development · Testing

## Test layers

| Layer        | Where                                            | What                                                              |
| ------------ | ------------------------------------------------ | ----------------------------------------------------------------- |
| Unit         | `tests/domain/`, `tests/infrastructure/`         | No I/O, no DB. Pure Python logic (signals, normalisation, scoring). |
| Integration  | `tests/application/`, `tests/presentation/api/`  | Uses a real Postgres (`cigars_test`) plus mocked external HTTP.    |
| Browser E2E  | `tests/e2e/web_smoke.py`                         | Drives a real Chromium via patchright against the live stack.      |

The `tests/conftest.py` builds and tears down a dedicated PG database
per test session, applying `Base.metadata.create_all` instead of
running Alembic for speed. `pgvector`, `citext` and `pg_trgm`
extensions are enabled before the schema is created.

## Running the suite

```bash
# Everything except network smoke tests (default)
uv run pytest

# Plus network tests (hits real customs sources)
uv run pytest -m network

# Subset: API only
uv run pytest tests/presentation/api -q

# Single test, debug mode
uv run pytest -k "test_match_cigar" -vv -s
```

## E2E browser test

The patchright-driven test under `tests/e2e/web_smoke.py` exercises
login → dashboard → cigars list → search → review queue → /me →
logout. Run it manually:

```bash
# In two terminals:
make api                                  # uvicorn :8000
cd web && npm run dev                     # vite  :3000

# In a third:
E2E_ADMIN_PASSWORD='s3cret' \
  uv run python tests/e2e/web_smoke.py
```

To watch the browser:

```bash
E2E_HEADLESS=0 uv run python tests/e2e/web_smoke.py
```

## CI behaviour

`.github/workflows/ci.yml` runs:

- `ruff check` + `ruff format --check`.
- `mypy src` (non-blocking — best-effort while we improve typing).
- `pytest -m "not network" --ignore=tests/integration`.
- `cd web && npm run lint && npm test --if-present && npm run build`.

Service containers (`pgvector/pgvector:pg16`, `redis:7-alpine`) are
brought up by GitHub Actions. SeaweedFS isn't (the few tests that
exercise S3 do it through a moto-style mock or skip with a `network`
marker).

## Adding a test

- Tests live next to the code they exercise, mirroring `src/`.
- Use the `clean_db` fixture from `conftest.py` whenever you touch
  Postgres — it truncates every table after the test.
- Use the `seeded_universe` fixture from `tests/presentation/api/
  conftest.py` when an API test needs a small reproducible catalogue +
  customs source + matched user.
- Mock the embedder rather than spinning up `sentence-transformers`
  (see `FakeEmbedder` in
  `tests/application/matching/test_match_cigar_to_customs.py`).

## Performance regressions

We don't have a perf benchmark suite yet. If a code path's latency
matters to you, drop a `tests/benchmarks/test_<name>.py` using
`pytest-benchmark` — it stays opt-in (`pytest -k benchmark`).
