# 5. React + Vite + shadcn for the web admin

Date: 2026-05-25

## Status

Accepted

## Context

The platform needed a small browser-based admin to:

- Browse the catalogue and customs data.
- Review the `PENDING_REVIEW` match queue and accept/reject entries.
- Trigger background jobs (customs refresh, matching rerun).

Hard constraints:

- Strong typing end-to-end (the API contract is generated from
  OpenAPI — we want the front to consume it without manual schema
  drift).
- Modern toolchain that fits in a Docker image.
- Tailwind-friendly so we can iterate quickly on a clean, accessible UI.

## Decision

We adopt:

- **Vite 5** as the build tool (instant dev server, ES modules, Rollup
  output).
- **React 18 + TypeScript strict** as the runtime + language.
- **shadcn-flavoured Tailwind components** copied into the repo
  (not an npm dependency) so we own the component code.
- **TanStack Query** v5 for server-state caching + revalidation.
- **React Router 6** for routing.
- **Zustand** for in-memory auth state.
- **React Hook Form + Zod** for form validation.
- **react-intl (FormatJS)** for i18n (en / fr).

Candidates considered:

| Option        | Why we did not pick it                                           |
| ------------- | ---------------------------------------------------------------- |
| **Next.js 14** | SSR adds operational complexity (Node runtime in prod) we don't need for an internal admin. |
| **Remix**     | Same SSR overhead.                                               |
| **SvelteKit** | Smaller talent pool; ecosystem (shadcn equivalent) less mature. |
| **HTMX + Jinja** | Server-side templating loses the optimistic-UI feel of the queue page. |
| **Streamlit / Gradio** | Not a real product UI; auth + RBAC bolt-ons are ugly. |

## Consequences

- The build produces a static SPA (~120 KB gzipped) served by nginx
  in production — minimal runtime footprint, easy to scale behind a
  CDN.
- The web container does not need a Node runtime at execution time.
- We accept React's churn rate (we're on React 18; upgrading to 19+
  will require attention to concurrent features).
- TypeScript strict prevents most footguns; the trade-off is more
  upfront declaration work on the OpenAPI types.
