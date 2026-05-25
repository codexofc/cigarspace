# Development · Release process

Cigarspace uses [release-please](https://github.com/googleapis/release-please)
with the `simple` strategy, driven by Conventional Commits.

## Versioning

We follow [Semantic Versioning 2.0](https://semver.org/):

- `MAJOR` — breaking change (API contract, schema we can't migrate
  forward, license shift).
- `MINOR` — backwards-compatible feature.
- `PATCH` — bug fix only.

The version lives in three places that must stay in sync:

- `pyproject.toml` (`[project].version`)
- `web/package.json` (`"version"`)
- `CHANGELOG.md` (latest section header)

Release-please automates this via a release PR whenever new Conventional
Commits land on `main`.

## Flow

1. Land Conventional Commits on `main` (PRs squash-merged with a
   conforming title work).
2. `.github/workflows/release.yml` runs on every push to `main`. If
   there are commits since the last tag, release-please opens a PR
   titled `chore(main): release <semver>` containing:
   - the bumped `pyproject.toml` + `web/package.json`,
   - a generated `CHANGELOG.md` entry,
   - a list of every commit since the previous tag.
3. Review the PR. Edit the changelog if anything reads poorly. Merge.
4. release-please tags the merge commit `v<semver>` and creates the
   GitHub Release.
5. `.github/workflows/docker.yml` is triggered by the `v*.*.*` tag and
   pushes:
   - `ghcr.io/codexofc/cigarspace:<semver>` (light)
   - `ghcr.io/codexofc/cigarspace:<semver>-demo`
   - matching `latest` / `latest-demo` tags (multi-arch amd64+arm64).

## Pre-1.0 conventions

For `0.x.y`, the team treats minor bumps as potentially breaking. From
1.0 onwards, semver applies strictly.

## Hot-fixing a released version

If `v1.4.2` has a critical bug:

```bash
git switch -c hotfix/v1.4.3 v1.4.2
# apply fix, commit with conventional message (fix: …)
git push -u origin hotfix/v1.4.3
# open PR → main; release-please will pick up the commit and propose v1.4.3.
```

Patches do not branch off `main` if `main` already has unreleased
work — release-please handles the cherry-picking.

## Things that block a release

- CI red on `main`.
- A failing migration in `migrations/versions/` — every release must
  apply cleanly from the last released schema.
- A breaking change without an ADR documenting it.
- Missing `CHANGELOG.md` entry (release-please refuses to bump if no
  Conventional Commits since the previous tag — that's by design).

## Manual release (escape hatch)

```bash
# Bump versions manually
sed -i '' 's/version = "1.4.2"/version = "1.4.3"/' pyproject.toml
sed -i '' 's/"version": "1.4.2"/"version": "1.4.3"/' web/package.json

# Write the changelog
$EDITOR CHANGELOG.md

git commit -am "chore(main): release 1.4.3"
git tag v1.4.3
git push origin main --tags
```

The docker workflow will still pick the tag and build the image.
