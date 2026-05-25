# Deployment · Docker

## Two image variants

Cigarspace ships two flavours of the all-in-one container, both built
from `docker/all-in-one.Dockerfile`:

| Tag                 | Includes                                  | When to use                          |
| ------------------- | ----------------------------------------- | ------------------------------------ |
| `cigarspace:latest` | API + arq worker + nginx + web SPA        | Production. External Postgres / Redis / S3. |
| `cigarspace:demo`   | All of the above + PostgreSQL 15+pgvector + Redis | Local demos, single-VM dev kicks. **Not production-grade** — data lives inside the container unless volumes are mounted. |

Both publish to GHCR via `.github/workflows/docker.yml` on every tag:

- `ghcr.io/codexofc/cigarspace:<semver>`
- `ghcr.io/codexofc/cigarspace:<semver>-demo`

## Build locally

```bash
# Production-grade
make build-light          # → cigarspace:latest

# Demo flavour
make build-demo           # → cigarspace:demo

# Multi-arch (CI does this automatically)
docker buildx build --platform linux/amd64,linux/arm64 \
  -f docker/all-in-one.Dockerfile -t cigarspace:latest .
```

## Run

### `:demo` — one-command quick-start

```bash
make demo-up              # docker compose -f docker/compose.demo.yml up
open http://localhost:8080
```

Bootstrap an admin from another terminal while the stack is up:

```bash
docker compose -f docker/compose.demo.yml exec cigarspace \
  /app/.venv/bin/cigarspace users create \
    --email admin@example.com --password 's3cret' --admin
```

### `:latest` — production-grade compose

`docker/compose.yml` brings up Postgres + Redis + SeaweedFS + the API
+ the web container as separate services. The Dockerfile builds the
same `cigarspace:latest` image used by `:demo` (without the embedded
DBs).

```bash
make up                   # core dependencies
make up-all               # full stack incl. app + web
```

## Environment variables

The image reads its configuration from environment. The most important
ones live in `.env.example`; the production-critical ones:

| Variable                            | Default              | Notes                                  |
| ----------------------------------- | -------------------- | -------------------------------------- |
| `APP_ENV`                           | `dev`                | Set to `prod` to enable hardening checks. |
| `POSTGRES_HOST / _PORT / _USER / _PASSWORD / _DB` | localhost defaults | Required.                              |
| `REDIS_HOST / _PORT / _DB`          | localhost / 6379 / 0 | Required.                              |
| `S3_ENDPOINT_URL / _BUCKET / _ACCESS_KEY_ID / _SECRET_ACCESS_KEY` | SeaweedFS local | S3-compatible target. |
| `API_JWT_SECRET`                    | `change-me…`         | **Must** be ≥ 32 bytes in prod; the API refuses to start otherwise. |
| `API_CORS_ORIGINS`                  | `["*"]`              | **Must** list explicit origins in prod. |
| `API_PORT` / `WEB_PORT`             | `8000` / `3000`      | Host port mapping for the two services in `compose.yml`. |
| `API_RATE_LIMIT_STORAGE`            | Redis DSN            | Set to `memory://` in tests / single-instance dev. |
| `API_WARM_EMBEDDER_ON_STARTUP`      | `false`              | If `true`, the worker pre-loads the 420 MB mpnet model at boot so the first `/cigars/search` doesn't pay the cold-start cost. |

## Healthchecks

- `cigarspace:latest` exposes `/api/v1/health` which returns 200 if
  Postgres, Redis and S3 respond, 503 otherwise. The compose file uses
  it for `healthcheck`.
- Inside the image, supervisord restarts any crashed sub-process (API,
  worker, nginx).

## Volumes

- `pg-data` (Postgres data, only in `:demo`).
- `redis-data` (Redis AOF, only in `:demo`).
- `seaweed-data` (only when SeaweedFS is the S3 target, which is the
  default in `compose.yml`).

`:demo` mounts both DBs to a single volume so a `docker compose down`
keeps the catalogue around between sessions.

## Upgrading

The `cigarspace-entrypoint` script runs `alembic upgrade head` at boot,
so a fresh container automatically migrates the schema. Downgrades are
out of scope — restore from a Postgres dump.
