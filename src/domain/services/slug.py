# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Pure slug generation — no external dependencies."""

from __future__ import annotations

import re
import unicodedata

_NON_ALPHANUM = re.compile(r"[^a-z0-9]+")
_TRIM_DASHES = re.compile(r"^-+|-+$")


def slugify(text: str, *, max_length: int = 200) -> str:
    """Convert an arbitrary string to a URL-safe slug.

    - Normalises Unicode to NFKD and drops combining marks (à → a, ñ → n).
    - Lowercases.
    - Collapses any run of non-alphanumeric characters to a single hyphen.
    - Strips leading/trailing hyphens.
    - Truncates to max_length (default 200).
    """

    if not text:
        raise ValueError("Cannot slugify an empty string")

    normalised = unicodedata.normalize("NFKD", text)
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii")
    lower = ascii_only.lower()
    dashed = _NON_ALPHANUM.sub("-", lower)
    trimmed = _TRIM_DASHES.sub("", dashed)

    if not trimmed:
        raise ValueError(f"String yielded an empty slug after normalisation: {text!r}")

    return trimmed[:max_length].rstrip("-")


def compose_slug(*parts: str, max_length: int = 200) -> str:
    """Slugify each part individually and join with hyphens (no double-dashing)."""

    pieces = [slugify(p, max_length=max_length) for p in parts if p]
    return slugify("-".join(pieces), max_length=max_length)
