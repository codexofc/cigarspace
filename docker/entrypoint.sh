#!/usr/bin/env bash
# Cigarspace all-in-one entrypoint:
# - waits briefly for Postgres + Redis to be reachable,
# - runs alembic upgrade head once at boot,
# - delegates to whatever was passed as CMD (supervisord by default).

set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"

log() { printf '[entrypoint] %s\n' "$*" >&2; }

wait_for() {
  local host="$1" port="$2" name="$3"
  for _ in $(seq 1 60); do
    if (echo > "/dev/tcp/${host}/${port}") 2>/dev/null; then
      log "${name} reachable at ${host}:${port}"
      return 0
    fi
    sleep 1
  done
  log "ERROR: ${name} not reachable at ${host}:${port} after 60s"
  return 1
}

# In the :demo image PG / Redis are siblings on 127.0.0.1 and supervisord
# brings them up — we still wait so migrations don't race.
wait_for "${POSTGRES_HOST}" "${POSTGRES_PORT}" "PostgreSQL"
wait_for "${REDIS_HOST}" "${REDIS_PORT}" "Redis" || true

log "applying alembic migrations"
cd /app && /app/.venv/bin/alembic upgrade head || {
  log "alembic upgrade failed — continuing so supervisord can still serve"
}

log "delegating to: $*"
exec "$@"
