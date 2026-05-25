# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Customs discovery port — find publications in a regulator's index."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any, ClassVar, Protocol

from pydantic import BaseModel, ConfigDict, Field


class DiscoveredPublication(BaseModel):
    """A publication seen on an index page, not yet fetched or parsed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    regulator_reference: str = Field(min_length=1, max_length=256)
    document_url: str = Field(min_length=1, max_length=2048)
    publication_date: date | None = None
    effective_date: date | None = None
    document_mime: str | None = Field(default=None, max_length=128)


class ICustomsDiscoveryAdapter(Protocol):
    """Implementation lives in `infrastructure/customs/discovery/`."""

    name: ClassVar[str]

    # API-backed adapters (e.g. legifrance-dila) handle their own auth and
    # HTTP verb (POST), so the generic GET pre-fetch in the use case must
    # be skipped — they set this to False.
    requires_index_fetch: ClassVar[bool] = True

    async def find_publications(
        self,
        *,
        index_html: str,
        index_url: str,
        config: dict[str, Any],
    ) -> Sequence[DiscoveredPublication]: ...
