# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] — 2026-05-25

First public release as **Cigarspace**.

### Added

- **Ingestion pipeline**: multi-merchant scraping (mistercigar.com,
  cigarpassion.ch) with a parser registry dispatching by domain.
  Resilient fetcher with tiered fallbacks (direct → HTTP proxy →
  ProtonVPN WireGuard sidecar → Tor SOCKS5).
- **Domain model**: canonical Cigar / Brand / CigarLine / Package /
  Media entities, blend components, tasting attributes, dimensions,
  flavor profile value objects.
- **Customs ingestion**: jurisdiction-neutral `CustomsSource` /
  `CustomsPublication` / `CustomsPriceEntry`. France adapter targets
  the Douane FR open-data CSV.
- **Hybrid matching**: pgvector + MPNet 768-d embeddings combined
  with trigram and structured signals via Reciprocal Rank Fusion.
  Human review queue preserves `HUMAN_*` verdicts across re-matches.
- **Public HTTP API**: FastAPI service exposing read endpoints for
  the catalogue and admin endpoints for the review queue and refresh
  jobs. OAuth2 password grant with rotating refresh tokens, RFC 7807
  errors, ETag/304, RFC 5988 pagination links, OpenAPI 3.1 generated.
- **Web admin UI**: React + Vite + TypeScript + shadcn/ui SPA with
  HttpOnly cookie auth, dashboard, cigar browser, hybrid search, and
  review queue.
- **i18n**: `react-intl` with English and French locales and an
  in-app language switcher.
- **Docker**: multi-stage `api`, `web`, and `all-in-one` images
  (light + demo variants); `docker compose` topology with Postgres
  (pgvector), Redis, SeaweedFS, optional gluetun/Tor profiles.
- **CI/CD**: GitHub Actions workflows for lint+test, multi-arch
  Docker buildx → GHCR, release-please, CodeQL, and OpenSSF Scorecard.
- **Documentation**: README with badges and Mermaid diagrams,
  architecture and data-model docs, five ADRs, deployment and
  development guides.
- **Community files**: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `SECURITY.md`, `SUPPORT.md`, GitHub issue forms, PR template,
  CODEOWNERS, Dependabot, FUNDING.

### Licensed

- Sources distributed under **PolyForm Noncommercial 1.0.0**.
- Parallel commercial path documented in `COMMERCIAL_LICENSE.md`.

[Unreleased]: https://github.com/codexofc/cigarspace/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/codexofc/cigarspace/releases/tag/v1.0.0
