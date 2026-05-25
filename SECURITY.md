# Security Policy

We take security seriously. Thank you for helping keep Cigarspace and
its users safe.

## Supported versions

Security fixes are issued for the latest minor release. Older releases
receive fixes only on a case-by-case basis.

| Version | Supported |
| ------- | --------- |
| 1.x     | ✅        |
| < 1.0   | ❌        |

## Reporting a vulnerability

**Please do not file a public GitHub issue for security reports.**

Use one of the private channels below:

1. **GitHub Security Advisories** (preferred) — open a draft advisory
   on the [Security tab][advisories] of the repository. This gives us
   a private space to coordinate the fix and a CVE if appropriate.
2. **Email** — write to `Michon.arthurperso@gmail.com` with the
   subject prefix `[cigarspace-security]`. PGP encryption is welcome
   but not required; if you would like to use it, ask in your first
   message and a key will be provided.

In your report, please include:

- a description of the issue and the impact,
- a minimal proof-of-concept or steps to reproduce,
- the affected version (commit SHA or release tag),
- any mitigations you have already identified.

## Response timeline

We aim to:

- acknowledge the report within **3 business days**,
- provide an initial assessment within **7 business days**,
- ship a fix or mitigation within **30 days** for high/critical issues
  (lower-severity issues may take longer).

These are best-effort targets for an open-source project, not a
contractual SLA. Commercial-license holders may negotiate a stricter
SLA — see [COMMERCIAL_LICENSE.md](./COMMERCIAL_LICENSE.md).

## Disclosure

We follow a **coordinated disclosure** model. Once a fix is available,
we will:

1. Release a patched version,
2. Publish a security advisory with credit to the reporter (unless
   anonymity is requested),
3. Request a CVE through GitHub when appropriate.

## Scope

In scope:

- The Cigarspace API, worker, web admin, and Docker images published
  by this project.
- The default `cigarspace-config` shipped in this repository.

Out of scope:

- Vulnerabilities in third-party dependencies — report those upstream
  (we track CVEs via Dependabot and pull in the patch).
- Issues that require an already-compromised host or stolen
  credentials.
- Self-hosted misconfigurations (e.g. exposing the admin port to the
  public internet without auth).

[advisories]: https://github.com/codexofc/cigarspace/security/advisories
