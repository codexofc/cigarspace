# 1. Record architecture decisions

Date: 2026-05-25

## Status

Accepted

## Context

We need a lightweight, durable way to capture the reasoning behind
architectural decisions. Discussion threads on PRs and Slack go cold;
code comments rot. Future maintainers (and future-us) need to know not
just *what* the system does but *why* it does it that way.

## Decision

We use Architecture Decision Records (ADRs) in the format described by
Michael Nygard:
[https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).

- Each ADR lives in `docs/adr/NNNN-short-name.md`, numbered sequentially.
- ADRs are immutable once accepted. If a decision is later changed, a
  new ADR supersedes the previous one and the older one is marked
  `Status: Superseded by NNNN`.
- Anything that materially affects developers (language, framework,
  storage engine, license, scaling model) needs an ADR.

## Consequences

- A reader navigating `docs/adr/` can reconstruct the design intent
  without spelunking the git log.
- Contributors are expected to add an ADR alongside a non-trivial PR
  (see `CONTRIBUTING.md`).
- The directory is the canonical source for "why does Cigarspace do X
  instead of Y?" questions.
