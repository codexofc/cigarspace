# 4. Source-available licensing (PolyForm Noncommercial + commercial on request)

Date: 2026-05-25

## Status

Accepted

## Context

We want the code to be public so the project can attract contributors,
be auditable, and serve as a reference implementation for the cigar
industry. We do **not** want anyone to be able to spin up a hosted
clone and resell it, or bundle Cigarspace into a closed commercial
product without engaging with the maintainers.

Common options on the spectrum:

| License | Commercial use? | Hosted SaaS reselling? | SPDX | Notes |
| --- | --- | --- | --- | --- |
| MIT / Apache-2.0 | Yes | Yes | ✓ | Maximum freedom, no leverage for sustainability. |
| AGPL-3.0 | Yes | Must release modifications | ✓ | OSI-approved but viral; scares some adopters. |
| Elastic License 2.0 | Internal yes, managed SaaS reselling no | No | ✗ (not OSI/SPDX-standard) | Used by Elastic, Sentry. |
| BUSL-1.1 | No for 4 years, then Apache-2.0 | No initially | ✓ | Sentry, CockroachDB, MariaDB. |
| **PolyForm Noncommercial 1.0.0** | No (never) | No | ✓ | n8n-style "fair-code". |

## Decision

We license Cigarspace under **PolyForm Noncommercial 1.0.0** (SPDX:
`PolyForm-Noncommercial-1.0.0`) and offer a **separate commercial
license on a case-by-case basis**.

- `LICENSE` carries the verbatim PolyForm Noncommercial text.
- `COMMERCIAL_LICENSE.md` documents what counts as commercial use and
  how to reach the maintainers.
- Every source file carries `SPDX-License-Identifier:
  PolyForm-Noncommercial-1.0.0` so automated tooling (REUSE,
  pre-commit) keeps us honest.
- `NOTICE` enumerates third-party dependency licenses.

## Consequences

- Hobby use, research, contributions and personal experimentation are
  fully permitted — no friction for the open-source community.
- Anyone building a product on top of Cigarspace contacts the
  maintainers to negotiate terms.
- The license is not OSI-approved, so we cannot claim "open source"
  in the strict sense; we use "source-available" everywhere instead.
- Dual licensing requires Contributor License clarity — handled by
  the DCO sign-off in `CONTRIBUTING.md`.
- If commercial demand grows, we can transition later to BUSL-1.1
  (auto-conversion to Apache after a delay) without breaking existing
  community use.
