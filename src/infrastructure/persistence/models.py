# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""SQLAlchemy ORM models — the persistence schema.

All tables live in the single `public` PG schema. Mapping to/from domain
entities is handled by mappers.py.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    ARRAY,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain.enums import (
    BlendComponentType,
    Confidence,
    CustomsMatchStatus,
    CustomsPublicationStatus,
    FormatCategory,
    Intensity,
    MatchMethod,
    MediaAssetType,
    MediaStatus,
)

# Dimensionality of the sentence-transformer used by the matching pipeline
# (paraphrase-multilingual-mpnet-base-v2 → 768). A bump requires a migration
# that drops/recreates the embedding columns.
EMBEDDING_DIM = 768
from infrastructure.persistence.base import Base, TimestampMixin

# ---------------------------------------------------------------------------
# Reusable column factories
# ---------------------------------------------------------------------------


def _pk_uuid() -> Mapped[UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid4)


def _fk_uuid(table: str, column: str = "id", *, nullable: bool = False) -> Mapped[UUID]:
    return mapped_column(
        Uuid,
        ForeignKey(f"{table}.{column}", ondelete="CASCADE"),
        nullable=nullable,
        index=True,
    )


# ---------------------------------------------------------------------------
# Brand / Line / Cigar
# ---------------------------------------------------------------------------


class BrandModel(Base, TimestampMixin):
    __tablename__ = "brand"

    id: Mapped[UUID] = _pk_uuid()
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country_origin: Mapped[str | None] = mapped_column(String(3), nullable=True)
    parent_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(255)), nullable=False, default=list)

    lines: Mapped[list[CigarLineModel]] = relationship(
        back_populates="brand",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CigarLineModel(Base, TimestampMixin):
    __tablename__ = "cigar_line"
    __table_args__ = (UniqueConstraint("brand_id", "slug", name="uq_cigar_line_brand_id_slug"),)

    id: Mapped[UUID] = _pk_uuid()
    brand_id: Mapped[UUID] = _fk_uuid("brand")
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_limited_edition: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String(255)), nullable=False, default=list)

    brand: Mapped[BrandModel] = relationship(back_populates="lines")
    cigars: Mapped[list[CigarModel]] = relationship(
        back_populates="line",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CigarModel(Base, TimestampMixin):
    __tablename__ = "cigar"

    id: Mapped[UUID] = _pk_uuid()
    line_id: Mapped[UUID] = _fk_uuid("cigar_line")

    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    vitola_name: Mapped[str] = mapped_column(String(120), nullable=False)
    vitola_factory_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    format_category: Mapped[FormatCategory] = mapped_column(
        SAEnum(FormatCategory, name="format_category", native_enum=True),
        nullable=False,
        default=FormatCategory.OTHER,
    )

    length_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    ring_gauge: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ring_gauge_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    weight_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    draw_resistance_cmh2o: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    wrapper_country: Mapped[str | None] = mapped_column(String(3), nullable=True)
    binder_country: Mapped[str | None] = mapped_column(String(3), nullable=True)
    filler_countries: Mapped[list[str]] = mapped_column(
        ARRAY(String(3)), nullable=False, default=list
    )

    strength: Mapped[Intensity | None] = mapped_column(
        SAEnum(Intensity, name="intensity_strength", native_enum=True), nullable=True
    )
    body: Mapped[Intensity | None] = mapped_column(
        SAEnum(Intensity, name="intensity_body", native_enum=True), nullable=True
    )
    flavor_profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    aging_potential_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_cuban: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_handmade: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_box_pressed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    discontinued_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Populated by the matching pipeline. NULL until embeddings are
    # built; HNSW index is defined in the corresponding Alembic migration.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    line: Mapped[CigarLineModel] = relationship(back_populates="cigars")
    blend_components: Mapped[list[BlendComponentModel]] = relationship(
        back_populates="cigar",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    media_assets: Mapped[list[MediaAssetModel]] = relationship(
        back_populates="cigar",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tasting_notes: Mapped[list[TastingNoteModel]] = relationship(
        back_populates="cigar",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CigarPackageModel(Base, TimestampMixin):
    __tablename__ = "cigar_package"
    __table_args__ = (
        UniqueConstraint("cigar_id", "source_url", name="uq_cigar_package_cigar_source"),
    )

    id: Mapped[UUID] = _pk_uuid()
    cigar_id: Mapped[UUID] = _fk_uuid("cigar")

    pack_size: Mapped[int] = mapped_column(Integer, nullable=False)
    source_domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    sku: Mapped[str | None] = mapped_column(String(128), nullable=True)
    price_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    price_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BlendComponentModel(Base, TimestampMixin):
    __tablename__ = "blend_component"

    id: Mapped[UUID] = _pk_uuid()
    cigar_id: Mapped[UUID] = _fk_uuid("cigar")

    component_type: Mapped[BlendComponentType] = mapped_column(
        SAEnum(BlendComponentType, name="blend_component_type", native_enum=True),
        nullable=False,
    )
    tobacco_origin: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tobacco_region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tobacco_variety: Mapped[str | None] = mapped_column(String(120), nullable=True)
    aging_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    source_confidence: Mapped[Confidence] = mapped_column(
        SAEnum(Confidence, name="confidence", native_enum=True),
        nullable=False,
        default=Confidence.UNVERIFIED,
    )

    cigar: Mapped[CigarModel] = relationship(back_populates="blend_components")


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------


class MediaBlobModel(Base, TimestampMixin):
    """Physical content of a media asset — keyed by BLAKE3 hash."""

    __tablename__ = "media_blob"

    content_hash: Mapped[str] = mapped_column(String(128), primary_key=True)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    height_px: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MediaAssetModel(Base, TimestampMixin):
    __tablename__ = "media_asset"

    id: Mapped[UUID] = _pk_uuid()
    cigar_id: Mapped[UUID] = _fk_uuid("cigar")

    asset_type: Mapped[MediaAssetType] = mapped_column(
        SAEnum(MediaAssetType, name="media_asset_type", native_enum=True), nullable=False
    )
    original_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    media_blob_hash: Mapped[str | None] = mapped_column(
        String(128),
        ForeignKey("media_blob.content_hash", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[MediaStatus] = mapped_column(
        SAEnum(MediaStatus, name="media_status", native_enum=True),
        nullable=False,
        default=MediaStatus.PENDING,
    )
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cigar: Mapped[CigarModel] = relationship(back_populates="media_assets")


# ---------------------------------------------------------------------------
# Tasting & sources
# ---------------------------------------------------------------------------


class SourceRecordModel(Base, TimestampMixin):
    __tablename__ = "source_record"

    id: Mapped[UUID] = _pk_uuid()
    cigar_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("cigar.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    source_domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_html_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class TastingNoteModel(Base, TimestampMixin):
    __tablename__ = "tasting_note"

    id: Mapped[UUID] = _pk_uuid()
    cigar_id: Mapped[UUID] = _fk_uuid("cigar")
    source_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("source_record.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    reviewer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_scale: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes_structured: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    pairing_recommendations: Mapped[list[str]] = mapped_column(
        ARRAY(String(255)), nullable=False, default=list
    )

    cigar: Mapped[CigarModel] = relationship(back_populates="tasting_notes")


# ---------------------------------------------------------------------------
# Customs (multi-country: FR / CH / …)
# ---------------------------------------------------------------------------


class CustomsSourceModel(Base, TimestampMixin):
    __tablename__ = "customs_source"

    id: Mapped[UUID] = _pk_uuid()
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    index_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    discovery_parser_name: Mapped[str] = mapped_column(String(128), nullable=False)
    extraction_parser_name: Mapped[str] = mapped_column(String(128), nullable=False)
    default_currency_code: Mapped[str] = mapped_column(String(3), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cron_expression: Mapped[str | None] = mapped_column(String(64), nullable=True)

    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_publication_seen_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class CustomsPublicationModel(Base, TimestampMixin):
    __tablename__ = "customs_publication"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "regulator_reference",
            name="uq_customs_publication_source_ref",
        ),
    )

    id: Mapped[UUID] = _pk_uuid()
    source_id: Mapped[UUID] = _fk_uuid("customs_source")
    regulator_reference: Mapped[str] = mapped_column(String(256), nullable=False)

    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    document_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    document_mime: Mapped[str | None] = mapped_column(String(128), nullable=True)

    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[CustomsPublicationStatus] = mapped_column(
        SAEnum(
            CustomsPublicationStatus,
            name="customs_publication_status",
            native_enum=True,
        ),
        nullable=False,
        default=CustomsPublicationStatus.DISCOVERED,
    )

    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    entries_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CustomsPriceEntryModel(Base, TimestampMixin):
    __tablename__ = "customs_price_entry"
    __table_args__ = (
        UniqueConstraint(
            "publication_id",
            "raw_brand_label",
            "raw_product_label",
            "packaging_description",
            name="uq_customs_price_entry_natural",
        ),
    )

    id: Mapped[UUID] = _pk_uuid()
    publication_id: Mapped[UUID] = _fk_uuid("customs_publication")

    country_code: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    homologation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    raw_brand_label: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    raw_product_label: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    packaging_description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    pack_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tax_class: Mapped[str | None] = mapped_column(String(64), nullable=True)

    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(64), nullable=False)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


class CigarCustomsMatchModel(Base, TimestampMixin):
    __tablename__ = "cigar_customs_match"
    __table_args__ = (
        UniqueConstraint("cigar_id", "customs_entry_id", name="uq_cigar_customs_match_cigar_entry"),
    )

    id: Mapped[UUID] = _pk_uuid()
    cigar_id: Mapped[UUID] = _fk_uuid("cigar")
    customs_entry_id: Mapped[UUID] = _fk_uuid("customs_price_entry")

    match_method: Mapped[MatchMethod] = mapped_column(
        SAEnum(MatchMethod, name="match_method", native_enum=True), nullable=False
    )
    score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    confidence: Mapped[Confidence] = mapped_column(
        SAEnum(Confidence, name="confidence_match", native_enum=True), nullable=False
    )
    status: Mapped[CustomsMatchStatus] = mapped_column(
        SAEnum(CustomsMatchStatus, name="customs_match_status", native_enum=True),
        nullable=False,
        default=CustomsMatchStatus.PENDING_REVIEW,
        index=True,
    )

    pack_size_bucket: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signals: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False, default=dict)

    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    matched_by: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


# ---------------------------------------------------------------------------
# API users (public HTTP API authentication)
# ---------------------------------------------------------------------------


class ApiUserModel(Base, TimestampMixin):
    __tablename__ = "api_user"
    __table_args__ = (UniqueConstraint("email", name="uq_api_user_email"),)

    id: Mapped[UUID] = _pk_uuid()
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RefreshTokenModel(Base):
    __tablename__ = "refresh_token"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_refresh_token_hash"),)

    id: Mapped[UUID] = _pk_uuid()
    user_id: Mapped[UUID] = _fk_uuid("api_user")
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
