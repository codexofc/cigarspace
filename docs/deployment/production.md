# Deployment · Production

This guide assumes you have managed Postgres + Redis + S3 instances and
want to ship `cigarspace:latest` to a small fleet of VMs or a
Kubernetes cluster.

## Topology

```
          ┌──────────────┐
          │  TLS proxy   │  (Caddy / nginx / Cloudflare)
          └─────┬────────┘
                │ :443 → :80
       ┌────────┴────────┐
       │  cigarspace     │  ×N replicas
       │  :latest        │   • nginx (SPA + /api proxy)
       │                 │   • uvicorn FastAPI
       │                 │   • arq worker (1 or scaled separately)
       └────┬────┬───┬───┘
            │    │   │
   ┌────────┘    │   └────────┐
   ▼             ▼            ▼
┌──────┐     ┌──────┐    ┌────────┐
│  PG  │     │ Redis│    │   S3   │
│ +pg- │     │      │    │ (R2 /  │
│vector│     │      │    │  S3…)  │
└──────┘     └──────┘    └────────┘
```

## Hardening checklist

The `lifespan` in `presentation/api/main.py` already fails-fast when
`APP_ENV=prod` and any of these are misconfigured. Before flipping to
prod, double-check:

- [ ] `API_JWT_SECRET` is at least 32 bytes of cryptographic randomness
      (`openssl rand -base64 48`).
- [ ] `API_CORS_ORIGINS` is an explicit allowlist (never `["*"]`).
- [ ] TLS terminates **in front of** the container — we propagate
      `X-Forwarded-Proto` so `cookies.py` flips the `Secure` flag on the
      refresh cookie correctly.
- [ ] `APP_ENV=prod` and `LOG_FORMAT=json` so logs are machine-readable.
- [ ] Postgres connection uses a non-superuser role with `INSERT /
      UPDATE / DELETE` on the application schema only.
- [ ] Redis is reachable only from the application VPC (no public bind).
- [ ] Outbound egress is allowed to the customs / merchant domains the
      worker scrapes; nothing else.

## Scaling

- **API**: stateless — scale horizontally behind a load balancer.
- **Worker (arq)**: stateless — scale horizontally; arq de-duplicates
  jobs via Redis. Embedding compute is CPU-heavy, so size workers with
  the matching workload in mind (1 vCPU per ~50 cigars/sec encoded).
- **Web (nginx)**: bundled inside the `cigarspace` image — no need for
  separate replicas unless you want a CDN cache layer above.
- **Postgres**: pgvector's HNSW handles our current data volumes
  comfortably on a small instance. Plan for read-replicas if `GET
  /cigars` / `/cigars/search` become hot.

## Background jobs

Cron schedules live in `infrastructure/workers/worker.py`:

| Job                              | Schedule              | Effect                                    |
| -------------------------------- | --------------------- | ----------------------------------------- |
| `customs_refresh_fr`             | Daily 06:00 UTC       | `refresh_customs_source_job("fr-douane-opendata")` |
| `customs_refresh_ch`             | Weekly Mon 07:00 UTC  | `refresh_customs_source_job("ch-ofdf")`   |

You can trigger any of them manually:

```bash
# CLI (inside the container)
cigarspace customs-discover --source fr-douane-opendata
cigarspace match-all

# Admin HTTP (with a bearer)
curl -X POST -H "Authorization: Bearer $ACCESS" \
  https://your.host/api/v1/customs-sources/fr-douane-opendata/refresh-jobs
```

## Backups

Cigarspace is mostly stateless except for PostgreSQL (catalogue +
embeddings + matches + users + tokens) and S3 (media blobs).

- Postgres: use your provider's automated snapshots; `pg_dump` weekly
  to cold storage if you self-host. Embeddings are derived data and
  can be rebuilt from the source text via `cigarspace embeddings-build
  --target all`, but it costs a CPU minute per 5k rows.
- S3 / SeaweedFS: media is content-addressed; lost objects can be
  re-fetched if the merchant page still exposes them, but the link
  history is lost — back up regularly.

## Observability

The image emits structlog JSON lines on stdout (`LOG_FORMAT=json`).
Ship them to your aggregator (Loki, Cloudwatch, Datadog, etc.) — every
line carries a `request_id` that you can correlate with the
`X-Request-Id` response header.

The `/api/v1/health` endpoint reports each dependency's state and is
suitable for both liveness and readiness probes.
