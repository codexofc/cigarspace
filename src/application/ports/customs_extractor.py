# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Customs extractor port — turn a publication document into price entries."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any, ClassVar, Protocol

from pydantic import BaseModel, ConfigDict, Field


class CustomsPriceExtraction(BaseModel):
    """One raw price line emitted by an extractor.

    The use case is responsible for stamping `publication_id`, `country_code`,
    `extracted_at` and `extractor_version` before persisting.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_brand_label: str = Field(min_length=1, max_length=255)
    raw_product_label: str = Field(min_length=1, max_length=255)
    packaging_description: str | None = Field(default=None, max_length=255)

    unit_price: Decimal = Field(ge=0)
    pack_size: int | None = Field(default=None, ge=1)
    unit_count: int | None = Field(default=None, ge=1)
    tax_class: str | None = Field(default=None, max_length=64)

    homologation_date: date | None = None
    effective_date: date | None = None


class ICustomsExtractorAdapter(Protocol):
    """Implementation lives in `infrastructure/customs/extractors/`."""

    name: ClassVar[str]
    version: ClassVar[str]

    # API-backed extractors (e.g. legifrance-dila-json) handle their own auth
    # and HTTP verb. The use case skips its generic GET when this is False and
    # calls `fetch_document` instead.
    requires_document_fetch: ClassVar[bool] = True

    async def extract(
        self,
        *,
        document_bytes: bytes,
        mime_type: str,
        default_currency: str,
        config: dict[str, Any],
    ) -> Iterable[CustomsPriceExtraction]: ...

    async def fetch_document(
        self,
        *,
        document_url: str,
        config: dict[str, Any],
    ) -> bytes:
        """Self-fetch hook. Only implementations with
        ``requires_document_fetch = False`` must override this."""
        ...
