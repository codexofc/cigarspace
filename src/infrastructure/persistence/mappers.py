# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Domain ↔ ORM mapping functions, centralized for auditability."""

from __future__ import annotations

from domain.entities.api_user import ApiUser, RefreshToken
from domain.entities.brand import Brand
from domain.entities.cigar import BlendComponent, Cigar
from domain.entities.cigar_line import CigarLine
from domain.entities.cigar_package import CigarPackage
from domain.entities.customs import (
    CigarCustomsMatch,
    CustomsPriceEntry,
    CustomsPublication,
    CustomsSource,
)
from domain.entities.media import MediaAsset
from domain.entities.media_blob import MediaBlob
from domain.entities.tasting import SourceRecord, TastingNote
from domain.value_objects.flavor_profile import FlavorProfile
from infrastructure.persistence.models import (
    ApiUserModel,
    BlendComponentModel,
    BrandModel,
    CigarCustomsMatchModel,
    CigarLineModel,
    CigarModel,
    CigarPackageModel,
    CustomsPriceEntryModel,
    CustomsPublicationModel,
    CustomsSourceModel,
    MediaAssetModel,
    MediaBlobModel,
    RefreshTokenModel,
    SourceRecordModel,
    TastingNoteModel,
)

# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------


def brand_to_domain(m: BrandModel) -> Brand:
    return Brand(
        id=m.id,
        slug=m.slug,
        name=m.name,
        country_origin=m.country_origin,
        parent_company=m.parent_company,
        founded_year=m.founded_year,
        is_active=m.is_active,
        aliases=list(m.aliases or []),
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def brand_to_model(e: Brand) -> BrandModel:
    return BrandModel(
        id=e.id,
        slug=e.slug,
        name=e.name,
        country_origin=e.country_origin,
        parent_company=e.parent_company,
        founded_year=e.founded_year,
        is_active=e.is_active,
        aliases=list(e.aliases),
    )


def apply_brand_to_model(m: BrandModel, e: Brand) -> None:
    m.slug = e.slug
    m.name = e.name
    m.country_origin = e.country_origin
    m.parent_company = e.parent_company
    m.founded_year = e.founded_year
    m.is_active = e.is_active
    m.aliases = list(e.aliases)


# ---------------------------------------------------------------------------
# CigarLine
# ---------------------------------------------------------------------------


def cigar_line_to_domain(m: CigarLineModel) -> CigarLine:
    return CigarLine(
        id=m.id,
        brand_id=m.brand_id,
        slug=m.slug,
        name=m.name,
        release_year=m.release_year,
        is_limited_edition=m.is_limited_edition,
        description=m.description,
        aliases=list(m.aliases or []),
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def cigar_line_to_model(e: CigarLine) -> CigarLineModel:
    return CigarLineModel(
        id=e.id,
        brand_id=e.brand_id,
        slug=e.slug,
        name=e.name,
        release_year=e.release_year,
        is_limited_edition=e.is_limited_edition,
        description=e.description,
        aliases=list(e.aliases),
    )


def apply_cigar_line_to_model(m: CigarLineModel, e: CigarLine) -> None:
    m.brand_id = e.brand_id
    m.slug = e.slug
    m.name = e.name
    m.release_year = e.release_year
    m.is_limited_edition = e.is_limited_edition
    m.description = e.description
    m.aliases = list(e.aliases)


# ---------------------------------------------------------------------------
# BlendComponent
# ---------------------------------------------------------------------------


def blend_to_domain(m: BlendComponentModel) -> BlendComponent:
    return BlendComponent(
        id=m.id,
        cigar_id=m.cigar_id,
        component_type=m.component_type,
        tobacco_origin=m.tobacco_origin,
        tobacco_region=m.tobacco_region,
        tobacco_variety=m.tobacco_variety,
        aging_years=m.aging_years,
        percentage=m.percentage,
        source_confidence=m.source_confidence,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def blend_to_model(e: BlendComponent, cigar_id: object | None = None) -> BlendComponentModel:
    return BlendComponentModel(
        id=e.id,
        cigar_id=cigar_id if cigar_id is not None else e.cigar_id,
        component_type=e.component_type,
        tobacco_origin=e.tobacco_origin,
        tobacco_region=e.tobacco_region,
        tobacco_variety=e.tobacco_variety,
        aging_years=e.aging_years,
        percentage=e.percentage,
        source_confidence=e.source_confidence,
    )


# ---------------------------------------------------------------------------
# Cigar
# ---------------------------------------------------------------------------


def cigar_to_domain(m: CigarModel) -> Cigar:
    return Cigar(
        id=m.id,
        line_id=m.line_id,
        slug=m.slug,
        full_name=m.full_name,
        vitola_name=m.vitola_name,
        vitola_factory_name=m.vitola_factory_name,
        format_category=m.format_category,
        length_mm=m.length_mm,
        ring_gauge=m.ring_gauge,
        ring_gauge_mm=m.ring_gauge_mm,
        weight_g=m.weight_g,
        draw_resistance_cmh2o=m.draw_resistance_cmh2o,
        wrapper_country=m.wrapper_country,
        binder_country=m.binder_country,
        filler_countries=list(m.filler_countries or []),
        strength=m.strength,
        body=m.body,
        flavor_profile=FlavorProfile.model_validate(m.flavor_profile or {}),
        aging_potential_years=m.aging_potential_years,
        is_cuban=m.is_cuban,
        is_handmade=m.is_handmade,
        is_box_pressed=m.is_box_pressed,
        release_year=m.release_year,
        discontinued_year=m.discontinued_year,
        last_scraped_at=m.last_scraped_at,
        created_at=m.created_at,
        updated_at=m.updated_at,
        blend_components=[blend_to_domain(b) for b in m.blend_components],
    )


def cigar_to_model(e: Cigar) -> CigarModel:
    model = CigarModel(
        id=e.id,
        line_id=e.line_id,
        slug=e.slug,
        full_name=e.full_name,
        vitola_name=e.vitola_name,
        vitola_factory_name=e.vitola_factory_name,
        format_category=e.format_category,
        length_mm=e.length_mm,
        ring_gauge=e.ring_gauge,
        ring_gauge_mm=e.ring_gauge_mm,
        weight_g=e.weight_g,
        draw_resistance_cmh2o=e.draw_resistance_cmh2o,
        wrapper_country=e.wrapper_country,
        binder_country=e.binder_country,
        filler_countries=list(e.filler_countries),
        strength=e.strength,
        body=e.body,
        flavor_profile=e.flavor_profile.model_dump(exclude_none=True),
        aging_potential_years=e.aging_potential_years,
        is_cuban=e.is_cuban,
        is_handmade=e.is_handmade,
        is_box_pressed=e.is_box_pressed,
        release_year=e.release_year,
        discontinued_year=e.discontinued_year,
        last_scraped_at=e.last_scraped_at,
    )
    model.blend_components = [blend_to_model(b, cigar_id=e.id) for b in e.blend_components]
    return model


def apply_cigar_to_model(m: CigarModel, e: Cigar) -> None:
    m.line_id = e.line_id
    m.slug = e.slug
    m.full_name = e.full_name
    m.vitola_name = e.vitola_name
    m.vitola_factory_name = e.vitola_factory_name
    m.format_category = e.format_category
    m.length_mm = e.length_mm
    m.ring_gauge = e.ring_gauge
    m.ring_gauge_mm = e.ring_gauge_mm
    m.weight_g = e.weight_g
    m.draw_resistance_cmh2o = e.draw_resistance_cmh2o
    m.wrapper_country = e.wrapper_country
    m.binder_country = e.binder_country
    m.filler_countries = list(e.filler_countries)
    m.strength = e.strength
    m.body = e.body
    m.flavor_profile = e.flavor_profile.model_dump(exclude_none=True)
    m.aging_potential_years = e.aging_potential_years
    m.is_cuban = e.is_cuban
    m.is_handmade = e.is_handmade
    m.is_box_pressed = e.is_box_pressed
    m.release_year = e.release_year
    m.discontinued_year = e.discontinued_year
    m.last_scraped_at = e.last_scraped_at


# ---------------------------------------------------------------------------
# Media
# ---------------------------------------------------------------------------


def media_to_domain(m: MediaAssetModel) -> MediaAsset:
    return MediaAsset(
        id=m.id,
        cigar_id=m.cigar_id,
        asset_type=m.asset_type,
        original_url=m.original_url,
        media_blob_hash=m.media_blob_hash,
        is_primary=m.is_primary,
        status=m.status,
        downloaded_at=m.downloaded_at,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def media_to_model(e: MediaAsset) -> MediaAssetModel:
    return MediaAssetModel(
        id=e.id,
        cigar_id=e.cigar_id,
        asset_type=e.asset_type,
        original_url=e.original_url,
        media_blob_hash=e.media_blob_hash,
        is_primary=e.is_primary,
        status=e.status,
        downloaded_at=e.downloaded_at,
    )


# ---------------------------------------------------------------------------
# MediaBlob
# ---------------------------------------------------------------------------


def media_blob_to_domain(m: MediaBlobModel) -> MediaBlob:
    return MediaBlob(
        content_hash=m.content_hash,
        storage_key=m.storage_key,
        mime_type=m.mime_type,
        byte_size=m.byte_size,
        width_px=m.width_px,
        height_px=m.height_px,
        first_seen_at=m.first_seen_at,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def media_blob_to_model(e: MediaBlob) -> MediaBlobModel:
    return MediaBlobModel(
        content_hash=e.content_hash,
        storage_key=e.storage_key,
        mime_type=e.mime_type,
        byte_size=e.byte_size,
        width_px=e.width_px,
        height_px=e.height_px,
        first_seen_at=e.first_seen_at,
    )


# ---------------------------------------------------------------------------
# Tasting / Source
# ---------------------------------------------------------------------------


def source_to_domain(m: SourceRecordModel) -> SourceRecord:
    return SourceRecord(
        id=m.id,
        cigar_id=m.cigar_id,
        source_domain=m.source_domain,
        source_url=m.source_url,
        http_status=m.http_status,
        fetched_at=m.fetched_at,
        raw_html_hash=m.raw_html_hash,
        parser_version=m.parser_version,
        extraction_confidence=m.extraction_confidence,
        raw_payload=m.raw_payload,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def source_to_model(e: SourceRecord) -> SourceRecordModel:
    return SourceRecordModel(
        id=e.id,
        cigar_id=e.cigar_id,
        source_domain=e.source_domain,
        source_url=e.source_url,
        http_status=e.http_status,
        fetched_at=e.fetched_at,
        raw_html_hash=e.raw_html_hash,
        parser_version=e.parser_version,
        extraction_confidence=e.extraction_confidence,
        raw_payload=e.raw_payload,
    )


def tasting_to_domain(m: TastingNoteModel) -> TastingNote:
    return TastingNote(
        id=m.id,
        cigar_id=m.cigar_id,
        source_id=m.source_id,
        reviewer_name=m.reviewer_name,
        published_at=m.published_at,
        score=m.score,
        score_scale=m.score_scale,
        notes_text=m.notes_text,
        notes_structured=m.notes_structured,
        pairing_recommendations=list(m.pairing_recommendations or []),
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def tasting_to_model(e: TastingNote) -> TastingNoteModel:
    return TastingNoteModel(
        id=e.id,
        cigar_id=e.cigar_id,
        source_id=e.source_id,
        reviewer_name=e.reviewer_name,
        published_at=e.published_at,
        score=e.score,
        score_scale=e.score_scale,
        notes_text=e.notes_text,
        notes_structured=e.notes_structured,
        pairing_recommendations=list(e.pairing_recommendations),
    )


# ---------------------------------------------------------------------------
# Customs
# ---------------------------------------------------------------------------


def customs_source_to_domain(m: CustomsSourceModel) -> CustomsSource:
    return CustomsSource(
        id=m.id,
        code=m.code,
        country_code=m.country_code,
        display_name=m.display_name,
        index_url=m.index_url,
        discovery_parser_name=m.discovery_parser_name,
        extraction_parser_name=m.extraction_parser_name,
        default_currency_code=m.default_currency_code,
        is_active=m.is_active,
        cron_expression=m.cron_expression,
        last_checked_at=m.last_checked_at,
        last_publication_seen_ref=m.last_publication_seen_ref,
        consecutive_failures=m.consecutive_failures,
        config_json=dict(m.config_json or {}),
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def customs_publication_to_domain(m: CustomsPublicationModel) -> CustomsPublication:
    return CustomsPublication(
        id=m.id,
        source_id=m.source_id,
        regulator_reference=m.regulator_reference,
        publication_date=m.publication_date,
        effective_date=m.effective_date,
        document_url=m.document_url,
        document_mime=m.document_mime,
        content_hash=m.content_hash,
        status=m.status,
        fetched_at=m.fetched_at,
        parsed_at=m.parsed_at,
        failure_reason=m.failure_reason,
        entries_count=m.entries_count,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def customs_price_to_domain(m: CustomsPriceEntryModel) -> CustomsPriceEntry:
    return CustomsPriceEntry(
        id=m.id,
        publication_id=m.publication_id,
        country_code=m.country_code,
        currency_code=m.currency_code,
        unit_price=m.unit_price,
        homologation_date=m.homologation_date,
        effective_date=m.effective_date,
        raw_brand_label=m.raw_brand_label,
        raw_product_label=m.raw_product_label,
        packaging_description=m.packaging_description,
        pack_size=m.pack_size,
        unit_count=m.unit_count,
        tax_class=m.tax_class,
        extracted_at=m.extracted_at,
        extractor_version=m.extractor_version,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def customs_source_to_model(e: CustomsSource) -> CustomsSourceModel:
    return CustomsSourceModel(
        id=e.id,
        code=e.code,
        country_code=e.country_code,
        display_name=e.display_name,
        index_url=e.index_url,
        discovery_parser_name=e.discovery_parser_name,
        extraction_parser_name=e.extraction_parser_name,
        default_currency_code=e.default_currency_code,
        is_active=e.is_active,
        cron_expression=e.cron_expression,
        last_checked_at=e.last_checked_at,
        last_publication_seen_ref=e.last_publication_seen_ref,
        consecutive_failures=e.consecutive_failures,
        config_json=dict(e.config_json),
    )


def customs_publication_to_model(e: CustomsPublication) -> CustomsPublicationModel:
    return CustomsPublicationModel(
        id=e.id,
        source_id=e.source_id,
        regulator_reference=e.regulator_reference,
        publication_date=e.publication_date,
        effective_date=e.effective_date,
        document_url=e.document_url,
        document_mime=e.document_mime,
        content_hash=e.content_hash,
        status=e.status,
        fetched_at=e.fetched_at,
        parsed_at=e.parsed_at,
        failure_reason=e.failure_reason,
        entries_count=e.entries_count,
    )


def customs_price_to_model(e: CustomsPriceEntry) -> CustomsPriceEntryModel:
    return CustomsPriceEntryModel(
        id=e.id,
        publication_id=e.publication_id,
        country_code=e.country_code,
        currency_code=e.currency_code,
        unit_price=e.unit_price,
        homologation_date=e.homologation_date,
        effective_date=e.effective_date,
        raw_brand_label=e.raw_brand_label,
        raw_product_label=e.raw_product_label,
        packaging_description=e.packaging_description,
        pack_size=e.pack_size,
        unit_count=e.unit_count,
        tax_class=e.tax_class,
        extracted_at=e.extracted_at,
        extractor_version=e.extractor_version,
    )


def customs_match_to_domain(m: CigarCustomsMatchModel) -> CigarCustomsMatch:
    return CigarCustomsMatch(
        id=m.id,
        cigar_id=m.cigar_id,
        customs_entry_id=m.customs_entry_id,
        match_method=m.match_method,
        score=m.score,
        confidence=m.confidence,
        status=m.status,
        pack_size_bucket=m.pack_size_bucket,
        signals=dict(m.signals or {}),
        matched_at=m.matched_at,
        matched_by=m.matched_by,
        reviewed_by=m.reviewed_by,
        reviewed_at=m.reviewed_at,
        notes=m.notes,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def customs_match_to_model(e: CigarCustomsMatch) -> CigarCustomsMatchModel:
    return CigarCustomsMatchModel(
        id=e.id,
        cigar_id=e.cigar_id,
        customs_entry_id=e.customs_entry_id,
        match_method=e.match_method,
        score=e.score,
        confidence=e.confidence,
        status=e.status,
        pack_size_bucket=e.pack_size_bucket,
        signals=dict(e.signals or {}),
        matched_at=e.matched_at,
        matched_by=e.matched_by,
        reviewed_by=e.reviewed_by,
        reviewed_at=e.reviewed_at,
        notes=e.notes,
    )


# ---------------------------------------------------------------------------
# CigarPackage
# ---------------------------------------------------------------------------


def cigar_package_to_domain(m: CigarPackageModel) -> CigarPackage:
    return CigarPackage(
        id=m.id,
        cigar_id=m.cigar_id,
        pack_size=m.pack_size,
        source_domain=m.source_domain,
        source_url=m.source_url,
        sku=m.sku,
        price_amount=m.price_amount,
        price_currency=m.price_currency,
        is_active=m.is_active,
        last_seen_at=m.last_seen_at,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def cigar_package_to_model(e: CigarPackage) -> CigarPackageModel:
    return CigarPackageModel(
        id=e.id,
        cigar_id=e.cigar_id,
        pack_size=e.pack_size,
        source_domain=e.source_domain,
        source_url=e.source_url,
        sku=e.sku,
        price_amount=e.price_amount,
        price_currency=e.price_currency,
        is_active=e.is_active,
        last_seen_at=e.last_seen_at,
    )


def apply_cigar_package_to_model(m: CigarPackageModel, e: CigarPackage) -> None:
    m.pack_size = e.pack_size
    m.source_domain = e.source_domain
    m.source_url = e.source_url
    m.sku = e.sku
    m.price_amount = e.price_amount
    m.price_currency = e.price_currency
    m.is_active = e.is_active
    m.last_seen_at = e.last_seen_at


# ---------------------------------------------------------------------------
# ApiUser / RefreshToken
# ---------------------------------------------------------------------------


def api_user_to_domain(m: ApiUserModel) -> ApiUser:
    return ApiUser(
        id=m.id,
        email=m.email,
        full_name=m.full_name,
        password_hash=m.password_hash,
        is_active=m.is_active,
        is_admin=m.is_admin,
        last_login_at=m.last_login_at,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def api_user_to_model(e: ApiUser) -> ApiUserModel:
    return ApiUserModel(
        id=e.id,
        email=e.email,
        full_name=e.full_name,
        password_hash=e.password_hash,
        is_active=e.is_active,
        is_admin=e.is_admin,
        last_login_at=e.last_login_at,
    )


def refresh_token_to_domain(m: RefreshTokenModel) -> RefreshToken:
    return RefreshToken(
        id=m.id,
        user_id=m.user_id,
        token_hash=m.token_hash,
        expires_at=m.expires_at,
        revoked_at=m.revoked_at,
        user_agent=m.user_agent,
        ip_address=str(m.ip_address) if m.ip_address is not None else None,
        created_at=m.created_at,
    )


def refresh_token_to_model(e: RefreshToken) -> RefreshTokenModel:
    return RefreshTokenModel(
        id=e.id,
        user_id=e.user_id,
        token_hash=e.token_hash,
        expires_at=e.expires_at,
        revoked_at=e.revoked_at,
        user_agent=e.user_agent,
        ip_address=e.ip_address,
    )
