# syntax=docker/dockerfile:1.7

# ---------------------------------------------------------------------------
# Stage 1 — Builder: install Python deps via uv into a virtualenv
# ---------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.5-python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Install dependencies first (better layer caching).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Install the project itself.
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 2 — Runtime: minimal slim image with the virtualenv copied in
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Non-root runtime user.
RUN groupadd --system --gid 1001 cigars \
 && useradd --system --uid 1001 --gid cigars --create-home --home-dir /home/cigars cigars \
 && mkdir -p /app /app/data \
 && chown -R cigars:cigars /app /home/cigars

WORKDIR /app

COPY --from=builder --chown=cigars:cigars /app/.venv /app/.venv
COPY --chown=cigars:cigars src ./src
COPY --chown=cigars:cigars migrations ./migrations
COPY --chown=cigars:cigars alembic.ini ./alembic.ini

USER cigars

ENTRYPOINT ["cigars"]
CMD ["--help"]
