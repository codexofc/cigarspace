SHELL := /bin/bash
.DEFAULT_GOAL := help

.PHONY: help bootstrap up down restart logs ps shell migrate revision \
        test lint format check info healthcheck clean nuke \
        api api-prod test-api

help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "}; /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---- Python / uv ---------------------------------------------------------

bootstrap: ## Install Python deps + generate uv.lock
	uv sync --all-groups

patchright-install: ## Download the patched Chromium for the L4 BrowserFetcher
	uv run patchright install chromium

lint: ## Run ruff lint
	uv run ruff check src tests

format: ## Format code and fix lint where possible
	uv run ruff format src tests
	uv run ruff check --fix src tests

check: ## Run mypy type checker
	uv run mypy src

test: ## Run unit tests (no live services, no network)
	uv run pytest -m "not integration and not e2e and not network"

test-all: ## Run unit + integration (requires running stack)
	uv run pytest -m "not network"

test-network: ## Run network smoke tests (hits real remote hosts)
	uv run pytest -m network

# ---- arq workers ---------------------------------------------------------

worker: ## Run the arq worker (foreground, Ctrl-C to stop)
	uv run cigars worker

# ---- Docker Compose stack -------------------------------------------------

up: ## Start postgres + redis + seaweedfs (and app once it builds)
	docker compose -f docker/compose.yml up -d postgres redis seaweedfs

up-all: ## Start the whole stack including app
	docker compose -f docker/compose.yml up -d --build

down: ## Stop the stack
	docker compose -f docker/compose.yml down

restart: down up ## Restart the stack

logs: ## Tail logs from all services
	docker compose -f docker/compose.yml logs -f --tail=100

ps: ## Show status of all services
	docker compose -f docker/compose.yml ps

shell: ## Open a bash shell inside the app image
	docker compose -f docker/compose.yml run --rm --entrypoint /bin/bash app

# ---- L2/L3 sidecars (opt-in via Compose profiles) -----------------------

vpn-up: ## Start gluetun (ProtonVPN L2 proxy on 127.0.0.1:8888)
	docker compose -f docker/compose.yml --profile vpn up -d gluetun

vpn-down: ## Stop gluetun
	docker compose -f docker/compose.yml --profile vpn stop gluetun

vpn-ip: ## Show the current outbound IP through the VPN
	@curl -sx http://127.0.0.1:8888 https://api.ipify.org && echo

tor-up: ## Start Tor SOCKS5 proxy (L3) on 127.0.0.1:9050
	docker compose -f docker/compose.yml --profile tor up -d tor

tor-down: ## Stop Tor
	docker compose -f docker/compose.yml --profile tor stop tor

tor-ip: ## Show the current Tor exit-node IP
	@curl -sx socks5h://127.0.0.1:9050 https://api.ipify.org && echo

# ---- Alembic --------------------------------------------------------------

migrate: ## Apply pending migrations (local: targets the exposed PG port)
	uv run alembic upgrade head

revision: ## Create a new auto-generated revision (usage: make revision m="message")
	@if [ -z "$(m)" ]; then echo "Usage: make revision m=\"your message\""; exit 2; fi
	uv run alembic revision --autogenerate -m "$(m)"

# ---- CLI shortcuts --------------------------------------------------------

info: ## Print app configuration (no secrets)
	uv run cigars info

healthcheck: ## Probe Postgres & Redis from the local Python env
	uv run cigars healthcheck

# ---- Cleanup --------------------------------------------------------------

clean: ## Stop stack and remove containers (volumes preserved)
	docker compose -f docker/compose.yml down

nuke: ## Stop stack and DELETE all volumes (destructive)
	docker compose -f docker/compose.yml down -v


# ---- Public HTTP API ---------------------------------------------------

api: ## Run the public API locally with hot-reload (uvicorn --reload)
	uv run uvicorn presentation.api.main:app --reload --host 0.0.0.0 --port 8000

api-prod: ## Run the API in production mode (workers, no reload)
	uv run uvicorn presentation.api.main:app --host 0.0.0.0 --port 8000 \
		--workers $${API_WORKERS:-2} --proxy-headers

test-api: ## Run only the API test suite
	uv run pytest tests/presentation/api -q

# ---- All-in-one image (release builds) -----------------------------------

build-light: ## Build the light all-in-one image (api + worker + web + nginx)
	docker buildx build -f docker/all-in-one.Dockerfile -t cigarspace:latest .

build-demo: ## Build the :demo image (light + embedded PG + Redis)
	docker buildx build -f docker/all-in-one.Dockerfile --target demo -t cigarspace:demo .

demo-up: ## Spin up the demo stack (browse http://localhost:8080)
	docker compose -f docker/compose.demo.yml up -d --build

demo-down: ## Stop the demo stack
	docker compose -f docker/compose.demo.yml down
