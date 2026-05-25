# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""All domain enumerations — single source of truth."""

from __future__ import annotations

from enum import StrEnum


class FormatCategory(StrEnum):
    ROBUSTO = "robusto"
    TORO = "toro"
    CORONA = "corona"
    PETIT_CORONA = "petit_corona"
    GRAN_CORONA = "gran_corona"
    DOUBLE_CORONA = "double_corona"
    CHURCHILL = "churchill"
    LONSDALE = "lonsdale"
    LANCERO = "lancero"
    PANETELA = "panetela"
    PERFECTO = "perfecto"
    TORPEDO = "torpedo"
    BELICOSO = "belicoso"
    FIGURADO = "figurado"
    DEMI_TASSE = "demi_tasse"
    OTHER = "other"


class Intensity(StrEnum):
    MILD = "mild"
    MILD_MEDIUM = "mild_medium"
    MEDIUM = "medium"
    MEDIUM_FULL = "medium_full"
    FULL = "full"


class BlendComponentType(StrEnum):
    WRAPPER = "wrapper"
    BINDER = "binder"
    FILLER_SECO = "filler_seco"
    FILLER_VOLADO = "filler_volado"
    FILLER_LIGERO = "filler_ligero"
    FILLER_MEDIO_TIEMPO = "filler_medio_tiempo"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNVERIFIED = "unverified"


class MediaAssetType(StrEnum):
    FRONT = "front"
    BAND = "band"
    FOOT = "foot"
    BOX_CLOSED = "box_closed"
    BOX_OPEN = "box_open"
    LIFESTYLE = "lifestyle"
    ASH = "ash"


class MediaStatus(StrEnum):
    PENDING = "pending"
    OK = "ok"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class MatchMethod(StrEnum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    EMBEDDING = "embedding"
    HYBRID = "hybrid"
    MANUAL = "manual"


class CustomsMatchStatus(StrEnum):
    """Decision workflow for a cigar↔customs match.

    AUTO_*: produced by the matcher pipeline alone.
    PENDING_REVIEW: confidence in the grey zone, awaits human triage.
    HUMAN_*: locked by an operator; never overwritten by re-matching.
    """

    AUTO_ACCEPTED = "auto_accepted"
    PENDING_REVIEW = "pending_review"
    AUTO_REJECTED = "auto_rejected"
    HUMAN_ACCEPTED = "human_accepted"
    HUMAN_REJECTED = "human_rejected"


class CustomsPublicationStatus(StrEnum):
    """Lifecycle of a discovered customs publication.

    DISCOVERED → FETCHED → PARSED → INGESTED. FAILED on hard error,
    SKIPPED when the content_hash matches what we already ingested.
    """

    DISCOVERED = "discovered"
    FETCHED = "fetched"
    PARSED = "parsed"
    INGESTED = "ingested"
    FAILED = "failed"
    SKIPPED = "skipped"
