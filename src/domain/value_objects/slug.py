# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Slug value type — URL-safe normalised identifier."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _validate(value: str) -> str:
    if not _SLUG_RE.fullmatch(value):
        raise ValueError(
            "Invalid slug: must be lowercase alphanumeric with single hyphen separators"
        )
    if len(value) > 200:
        raise ValueError("Slug too long (max 200 chars)")
    return value


Slug = Annotated[str, AfterValidator(_validate)]
