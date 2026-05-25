# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Customs domain — multi-country (France, Switzerland, …) tobacco pricing.

Architecture:
- `CustomsSource`     : a regulatory authority's publication channel
                        (e.g. France/Légifrance JORF, Switzerland/OFDF).
- `CustomsPublication`: a single document issued by that source
                        (e.g. one JORF arrêté homologuant les prix).
- `CustomsPriceEntry` : a single price line inside a publication
                        (one cigar / packaging / unit price).
- `CigarCustomsMatch` : audited link between a canonical Cigar and a price
                        entry (kept jurisdiction-neutral).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from domain.enums import (
    Confidence,
    CustomsMatchStatus,
    CustomsPublicationStatus,
    MatchMethod,
)


class CustomsSource(BaseModel):
    """A regulatory channel publishing tobacco price homologations."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    code: str = Field(min_length=1, max_length=64)  # "fr-legifrance-jorf"
    country_code: str = Field(min_length=2, max_length=2)  # ISO 3166-1 alpha-2
    display_name: str = Field(min_length=1, max_length=255)

    index_url: str = Field(min_length=1, max_length=2048)
    discovery_parser_name: str = Field(min_length=1, max_length=128)
    extraction_parser_name: str = Field(min_length=1, max_length=128)
    default_currency_code: str = Field(min_length=3, max_length=3)  # ISO 4217

    is_active: bool = True
    cron_expression: str | None = Field(default=None, max_length=64)

    last_checked_at: datetime | None = None
    last_publication_seen_ref: str | None = Field(default=None, max_length=256)
    consecutive_failures: int = Field(default=0, ge=0)

    config_json: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime | None = None
    updated_at: datetime | None = None


class CustomsPublication(BaseModel):
    """One regulatory document discovered for a source (e.g. one JORF arrêté)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    regulator_reference: str = Field(min_length=1, max_length=256)  # NOR JORF, OFDF n°, …
    publication_date: date | None = None
    effective_date: date | None = None

    document_url: str = Field(min_length=1, max_length=2048)
    document_mime: str | None = Field(default=None, max_length=128)

    content_hash: str | None = Field(default=None, max_length=128)  # blake2b hex
    status: CustomsPublicationStatus = CustomsPublicationStatus.DISCOVERED

    fetched_at: datetime | None = None
    parsed_at: datetime | None = None
    failure_reason: str | None = None
    entries_count: int = Field(default=0, ge=0)

    created_at: datetime | None = None
    updated_at: datetime | None = None


class CustomsPriceEntry(BaseModel):
    """One price line extracted from a regulatory publication."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    publication_id: UUID

    country_code: str = Field(min_length=2, max_length=2)
    currency_code: str = Field(min_length=3, max_length=3)
    unit_price: Decimal = Field(ge=0)

    homologation_date: date | None = None
    effective_date: date | None = None

    raw_brand_label: str = Field(min_length=1, max_length=255)
    raw_product_label: str = Field(min_length=1, max_length=255)
    packaging_description: str | None = Field(default=None, max_length=255)

    pack_size: int | None = Field(default=None, ge=1)
    unit_count: int | None = Field(default=None, ge=1)
    tax_class: str | None = Field(default=None, max_length=64)

    extracted_at: datetime
    extractor_version: str = Field(min_length=1, max_length=64)

    created_at: datetime | None = None
    updated_at: datetime | None = None


class CigarCustomsMatch(BaseModel):
    """Audited link between a canonical cigar and a customs price entry.

    ``signals`` records each sub-score the matcher computed (exact, fuzzy,
    vector, pack_compat) so the decision can be audited and the weights
    re-tuned without re-running the heavy embedding step.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    cigar_id: UUID
    customs_entry_id: UUID

    match_method: MatchMethod
    score: Decimal = Field(ge=0, le=1)
    confidence: Confidence
    status: CustomsMatchStatus = CustomsMatchStatus.PENDING_REVIEW

    pack_size_bucket: int | None = Field(default=None, ge=1)
    signals: dict[str, float] = Field(default_factory=dict)

    matched_at: datetime
    matched_by: str = Field(min_length=1, max_length=128)  # matcher version tag
    reviewed_by: str | None = Field(default=None, max_length=128)
    reviewed_at: datetime | None = None
    notes: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None
