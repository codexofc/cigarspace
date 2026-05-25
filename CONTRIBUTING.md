# Contributing to Cigarspace

Thanks for considering a contribution! This document is **strict** on
purpose — Cigarspace is a long-lived project with a small core team, and
clean contributions cost everyone less time than negotiating a sloppy
patch.

Before sending a Pull Request, please read this file end-to-end.

## Code of Conduct

This project follows the [Contributor Covenant 2.1](./CODE_OF_CONDUCT.md).
Disrespectful behaviour leads to immediate action. No second warnings.

## License + commercial use

Cigarspace is released under [PolyForm Noncommercial 1.0.0](./LICENSE).
By submitting a contribution, you agree that:

1. You are the author of the contribution, or you have the right to
   contribute it.
2. Your contribution is licensed under the same terms as the project.
3. If your contribution is non-trivial, you add the **Developer
   Certificate of Origin** sign-off line at the bottom of each commit
   message:
   ```
   Signed-off-by: Jane Doe <jane.doe@example.com>
   ```
   Use `git commit -s` to add it automatically.

For commercial use of the software, see
[COMMERCIAL_LICENSE.md](./COMMERCIAL_LICENSE.md).

## What we accept

| Contribution                                            | Welcome?       |
| ------------------------------------------------------- | -------------- |
| Bug reports with a reproducer                           | ✅              |
| Bug fixes with tests                                    | ✅              |
| New cigar merchant parser (with fixtures)               | ✅              |
| New customs source adapter (with fixtures)              | ✅              |
| API endpoint additions consistent with REST conventions | ✅              |
| Documentation improvements                              | ✅              |
| Tests for under-covered modules                         | ✅              |
| Architecture refactors not previously discussed         | ❌ open an ADR first |
| New runtime dependencies without strong rationale       | ❌              |
| UI redesigns or branding changes                        | ❌ owner-only   |
| Breaking changes to the public API                      | ❌ owner-only   |

For anything in the "owner-only" rows: open a GitHub
**Discussion** first.

## Workflow

### 1. Setup

```bash
git clone https://github.com/codexofc/cigarspace.git
cd cigarspace

# Python (uv recommended)
uv sync --all-groups
uv run pre-commit install

# Frontend
cd web && npm install && cd ..

# Infra (Postgres + pgvector, Redis, SeaweedFS)
make up
make migrate
```

### 2. Branch naming

```
feat/<short-description>       new feature
fix/<short-description>        bug fix
docs/<short-description>       docs only
chore/<short-description>      tooling, deps, CI
refactor/<short-description>   no behaviour change
test/<short-description>       test-only changes
```

### 3. Conventional Commits

Every commit message must follow
[Conventional Commits 1.0](https://www.conventionalcommits.org/):

```
feat(api): expose /matches summary endpoint
fix(parser): handle pack_size suffix without comma
docs(adr): record hybrid search decision
chore(deps): bump rapidfuzz to 3.14
```

The changelog is auto-generated from these messages by
`release-please`, so deviating breaks the release pipeline.

### 4. Pull Request checklist

A PR is ready when **all** of the following are true:

- [ ] Branch is up to date with `main`.
- [ ] `make lint` is green (ruff + mypy + eslint + prettier).
- [ ] `make test-all` is green (or you explain which fixtures need
      Docker).
- [ ] You added or updated tests for new behaviour.
- [ ] You added or updated docs for new behaviour.
- [ ] Conventional Commits in every commit.
- [ ] DCO sign-off in every commit.
- [ ] PR description fills the template.
- [ ] No new third-party dependency without a one-line rationale.
- [ ] No secrets in the diff (`pre-commit` runs trufflehog).

### 5. Reviews

- Reviews focus on correctness, security, and adherence to the
  conventions described in `docs/architecture.md`.
- Two-way conversation in PR comments; please respond rather than
  silently pushing fixes.
- Approval requires at least one core maintainer.

## Testing matrix

| Layer        | Command                                           | Notes                              |
| ------------ | ------------------------------------------------- | ---------------------------------- |
| Unit (BE)    | `uv run pytest -m "not integration and not network"` | No services required             |
| Integration  | `uv run pytest -m "not network"`                  | Needs Postgres + Redis             |
| API (BE)     | Included in pytest under `tests/presentation/api/` | Spins ASGI in-process              |
| Lint (BE)    | `uv run ruff check src tests`                     | Format: `uv run ruff format`       |
| Types (BE)   | `uv run mypy src`                                 |                                    |
| Unit (FE)    | `cd web && npm test`                              |                                    |
| Lint (FE)    | `cd web && npm run lint`                          |                                    |
| Build (FE)   | `cd web && npm run build`                         |                                    |
| End-to-end   | `uv run python tests/e2e/web_smoke.py`            | Needs API + Vite up                |

## When to open an ADR

If you propose a change that affects:

- A choice that is hard to reverse (database engine, language, license,
  major framework upgrade)
- A trade-off the team will reference later (e.g. how matches are scored)

…drop an ADR in `docs/adr/NNNN-short-name.md` (Michael Nygard format).
Existing examples live in `docs/adr/`.

## Reporting security issues

Do **not** open a GitHub issue for a security report. Use
GitHub's Private Vulnerability Reporting on this repository, or email
`Michon.arthurperso@gmail.com`. See [SECURITY.md](./SECURITY.md) for
the full process.

## Triage labels

- `good first issue` — small, well-scoped, ideal first PR.
- `help wanted` — we welcome external contributions on this issue.
- `needs-repro` — bug reports waiting for a reproducer.
- `pinned` — long-running issue; expect slow responses.

Welcome aboard.
