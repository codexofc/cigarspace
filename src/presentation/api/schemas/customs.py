# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Customs response schemas (sources / publications / entries)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.enums import CustomsPublicationStatus
from presentation.api.schemas.base import Links


class CustomsSourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    code: str = Field(examples=["fr-douane-opendata"])
    country_code: str
    display_name: str
    index_url: str
    discovery_parser_name: str
    extraction_parser_name: str
    default_currency_code: str
    is_active: bool
    cron_expression: str | None = None
    last_checked_at: datetime | None = None
    last_publication_seen_ref: str | None = None
    consecutive_failures: int
    config_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    links: Links = Field(alias="_links")


class CustomsPublicationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_id: UUID
    regulator_reference: str = Field(examples=["FR-DOUANE-2026-06-01"])
    publication_date: date | None = None
    effective_date: date | None = None
    document_url: str
    document_mime: str | None = None
    content_hash: str | None = None
    status: CustomsPublicationStatus
    fetched_at: datetime | None = None
    parsed_at: datetime | None = None
    failure_reason: str | None = None
    entries_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    links: Links = Field(alias="_links")


class CustomsEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    publication_id: UUID
    country_code: str
    currency_code: str
    unit_price: Decimal
    homologation_date: date | None = None
    effective_date: date | None = None
    raw_brand_label: str
    raw_product_label: str
    packaging_description: str | None = None
    pack_size: int | None = None
    unit_count: int | None = None
    tax_class: str | None = None
    extracted_at: datetime
    extractor_version: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    links: Links = Field(alias="_links")
