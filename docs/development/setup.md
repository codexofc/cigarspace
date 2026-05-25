# Development · Local setup

## Prerequisites

- Python 3.12 (managed via `uv`).
- Node 20 + npm (for the web admin).
- Docker / OrbStack (Postgres + Redis + SeaweedFS).
- A unix-y shell. macOS and Linux are the supported developer
  environments; Windows works under WSL2.

Install [uv](https://docs.astral.sh/uv/) once:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Clone + install

```bash
git clone https://github.com/codexofc/cigarspace.git
cd cigarspace

# Python dependencies (incl. dev + test groups)
uv sync --all-groups

# Pre-commit hooks
uv run pre-commit install

# Frontend
cd web && npm install && cd ..
```

## Bring up the data plane

```bash
cp .env.example .env       # tweak if needed
make up                    # Postgres + Redis + SeaweedFS
make migrate               # alembic upgrade head
```

## Run the stack

```bash
make api                   # uvicorn --reload on :8000
make worker                # arq worker (Ctrl-C to stop, in another terminal)

# Frontend (in another terminal)
cd web && npm run dev      # vite on :3000, proxies /api → :8000
```

## First user

```bash
uv run cigarspace users create \
  --email admin@example.com --password 's3cret' --admin
```

Then open `http://localhost:3000/login` and log in.

## Useful CLI commands

```bash
uv run cigarspace --help                              # surface map
uv run cigarspace info                                # config + counts
uv run cigarspace healthcheck                         # DB + Redis ping
uv run cigarspace customs-seed                        # load customs_sources.yaml
uv run cigarspace customs-status                      # source state table
uv run cigarspace ingest-url <merchant URL>           # scrape one product
uv run cigarspace crawl-listing <category URL>        # walk a listing
uv run cigarspace embeddings-build --target all       # encode missing rows
uv run cigarspace match-all                           # rerun matcher
uv run cigarspace match-review --limit 20             # peek the queue
```

## Project layout

```
src/
  domain/            Pure Pydantic entities (no I/O).
  application/       Ports (Protocols) + use cases.
  infrastructure/    Concrete adapters (DB, HTTP, parsers, customs, matching).
  presentation/      CLI + HTTP API entry points.
tests/               pytest suites, mirrored to src/ layout.
web/                 React + Vite + TS SPA.
migrations/          Alembic revisions.
docker/              Dockerfiles, compose files, supervisord configs.
docs/                This documentation tree (incl. ADRs).
branding/            Logo + favicon SVGs.
```

## When in doubt

- Architectural questions → `docs/architecture.md` and `docs/adr/`.
- Data shape → `docs/data-model.md`.
- Why the matcher said X → `docs/matching-pipeline.md`.
- How a customs source is wired → `docs/customs-sources.md`.
- "How do I contribute?" → `CONTRIBUTING.md`.
- "I think I found a security bug" → `SECURITY.md` (do not open an
  issue).
