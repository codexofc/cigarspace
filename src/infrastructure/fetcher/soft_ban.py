# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Soft-ban detection — recognise HTTP 200 responses that are actually a
WAF / captcha challenge, not the page we asked for.

Common patterns:
- Cloudflare interstitial    : "Just a moment...", "Checking your browser"
- Cloudflare turnstile/captcha : <div class="cf-turnstile">, "cf-challenge-running"
- Akamai bot manager         : "Pardon Our Interruption"
- DataDome captcha           : "datadome", "_dd_g="
- PerimeterX                 : "px-captcha"
- Generic                    : "Access Denied", "robot or human", "verify you are human"

The detector returns a SoftBanSignal describing what was matched, or None.
A caller (TieredFetcher / orchestrator) typically converts a hit into a
ForbiddenError to trigger tier escalation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# (pattern, label) — patterns are case-insensitive substrings unless they start with "re:"
_PATTERNS: tuple[tuple[str, str], ...] = (
    ("just a moment", "cloudflare_interstitial"),
    ("checking your browser", "cloudflare_interstitial"),
    ("attention required! | cloudflare", "cloudflare_block"),
    ("cf-challenge-running", "cloudflare_challenge"),
    ("cf-turnstile", "cloudflare_turnstile"),
    ("__cf_chl_", "cloudflare_challenge"),
    ("ddg_8_test", "datadome_cookie_test"),
    ("datadome", "datadome_block"),
    ("px-captcha", "perimeterx_captcha"),
    ("pardon our interruption", "akamai_bot_manager"),
    ("verify you are human", "generic_captcha"),
    ("are you a robot", "generic_captcha"),
    ("access denied", "generic_access_denied"),
    ("forbidden", "generic_forbidden_text"),
)

# Compile once
_RAW_NEEDLES: tuple[tuple[bytes, str], ...] = tuple(
    (needle.encode("ascii"), label) for needle, label in _PATTERNS
)

_HTML_CONTENT_RE = re.compile(rb"<(html|body)\b", re.IGNORECASE)


@dataclass(frozen=True)
class SoftBanSignal:
    label: str
    matched_pattern: str


class SoftBanDetector:
    """Stateless detector — safe to share across requests."""

    def __init__(
        self,
        *,
        extra_patterns: tuple[tuple[str, str], ...] = (),
        max_scan_bytes: int = 200_000,
    ) -> None:
        if max_scan_bytes < 1024:
            raise ValueError("max_scan_bytes must be >= 1024")
        self._needles = _RAW_NEEDLES + tuple(
            (p.lower().encode("ascii"), label) for p, label in extra_patterns
        )
        self._max_scan = max_scan_bytes

    def inspect(self, *, content_type: str, body: bytes) -> SoftBanSignal | None:
        """Inspect the response body. Returns a signal if a ban pattern matches."""

        # Only inspect HTML / text responses. Binary payloads (images, PDFs) are skipped.
        ct = content_type.lower()
        if "html" not in ct and "text/" not in ct:
            return None

        chunk = body[: self._max_scan].lower()

        # Cheap guard: if it doesn't even look like HTML, bail
        if not _HTML_CONTENT_RE.search(chunk):
            # short bodies with no <html>/<body> are still candidates for captcha snippets
            if len(body) > 2048:
                return None

        for needle, label in self._needles:
            if needle in chunk:
                return SoftBanSignal(label=label, matched_pattern=needle.decode("ascii"))
        return None
