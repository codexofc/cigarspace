# syntax=docker/dockerfile:1.7
#
# Cigarspace all-in-one image — bundles the API, the arq worker, and the
# nginx-served web SPA in a single container. PostgreSQL (with pgvector),
# Redis and an S3-compatible object store still run as **external** services
# in `:latest`. The `:demo` variant adds embedded PostgreSQL + Redis for a
# one-command quick start; see `docker/compose.demo.yml`.
#
# Build (light, recommended for production):
#   docker buildx build -f docker/all-in-one.Dockerfile -t cigarspace:latest .
#
# Build (demo, embedded PG + Redis):
#   docker buildx build -f docker/all-in-one.Dockerfile --target demo \
#     -t cigarspace:demo .

# --- 1. Build the SPA --------------------------------------------------------
FROM node:20-alpine AS web-builder
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY web/. ./
RUN npm run build

# --- 2. Resolve Python deps + install package -------------------------------
FROM python:3.12-slim AS py-builder
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*
RUN pip install uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --no-dev --frozen --no-install-project && \
    uv pip install --no-deps -e .

# --- 3a. Light runtime — API + worker + web (no embedded data services) -----
FROM python:3.12-slim AS light
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    APP_ENV=prod \
    LOG_FORMAT=json
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        nginx supervisor ca-certificates libpq5 curl tini && \
    rm -rf /var/lib/apt/lists/* && \
    rm -f /etc/nginx/sites-enabled/default
WORKDIR /app
COPY --from=py-builder /app /app
COPY --from=web-builder /web/dist /usr/share/nginx/html
COPY docker/nginx/all-in-one.conf /etc/nginx/conf.d/cigarspace.conf
COPY docker/supervisord/cigarspace.conf /etc/supervisor/conf.d/cigarspace.conf
COPY docker/entrypoint.sh /usr/local/bin/cigarspace-entrypoint
RUN chmod +x /usr/local/bin/cigarspace-entrypoint
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost/api/v1/health || exit 1
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/cigarspace-entrypoint"]
CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf", "-n"]

# --- 3b. Demo runtime — adds PostgreSQL + pgvector + Redis ------------------
FROM light AS demo
ENV POSTGRES_HOST=127.0.0.1 \
    POSTGRES_USER=cigars \
    POSTGRES_PASSWORD=cigars \
    POSTGRES_DB=cigars \
    REDIS_HOST=127.0.0.1
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        postgresql-15 postgresql-15-pgvector redis-server gnupg && \
    rm -rf /var/lib/apt/lists/*
COPY docker/supervisord/cigarspace-demo.conf /etc/supervisor/conf.d/cigarspace-demo.conf
# Demo persists data inside a single volume; production should not use :demo.
VOLUME ["/var/lib/postgresql", "/var/lib/redis"]
