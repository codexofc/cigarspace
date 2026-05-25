# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Mapping helpers : ProductExtraction (merchant-flavoured) → domain entities.

Kept here in `application/services/` because the conversion is policy
(business rules: how a "Module: Churchill" string maps to FormatCategory)
not infrastructure. Pure functions, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlparse

from application.ports.parser import ProductExtraction
from domain.enums import (
    BlendComponentType,
    Confidence,
    FormatCategory,
    Intensity,
)
from domain.entities.cigar import BlendComponent, Cigar
from domain.services.slug import compose_slug, slugify

# ---------------------------------------------------------------------------
# Countries — merchant labels (mostly French) → ISO 3166-1 alpha-3
# ---------------------------------------------------------------------------

_COUNTRY_ALIASES: dict[str, str] = {
    "république dominicaine": "DOM",
    "republique dominicaine": "DOM",
    "rep. dominicaine": "DOM",
    "saint-domingue": "DOM",
    "nicaragua": "NIC",
    "honduras": "HND",
    "cuba": "CUB",
    "équateur": "ECU",
    "equateur": "ECU",
    "ecuador": "ECU",
    "mexique": "MEX",
    "mexico": "MEX",
    "brésil": "BRA",
    "bresil": "BRA",
    "brazil": "BRA",
    "états-unis": "USA",
    "etats-unis": "USA",
    "usa": "USA",
    "cameroun": "CMR",
    "indonésie": "IDN",
    "indonesie": "IDN",
    "philippines": "PHL",
    "italie": "ITA",
    "péru": "PER",
    "perou": "PER",
    "panama": "PAN",
    "costa rica": "CRI",
    "venezuela": "VEN",
    "colombie": "COL",
}


def map_country(label: str | None) -> str | None:
    if not label:
        return None
    key = label.strip().lower()
    return _COUNTRY_ALIASES.get(key)


# ---------------------------------------------------------------------------
# Format category — merchant "Module" → FormatCategory
# ---------------------------------------------------------------------------

_FORMAT_ALIASES: dict[str, FormatCategory] = {
    # ─── Robusto family (~125 mm × ring 48-54) ─────────────────────────
    "robusto": FormatCategory.ROBUSTO,
    "robusto gordo": FormatCategory.ROBUSTO,
    "robusto extra": FormatCategory.ROBUSTO,
    "petit robusto": FormatCategory.ROBUSTO,
    # ─── Toro family (~150 mm × ring 50-56) ────────────────────────────
    "toro": FormatCategory.TORO,
    "gran toro": FormatCategory.TORO,
    "toro gordo": FormatCategory.TORO,
    "gordo": FormatCategory.TORO,  # 60+ ring gauge toro
    "double gordo": FormatCategory.TORO,
    "magnum": FormatCategory.TORO,
    "presidente": FormatCategory.TORO,
    # ─── Corona family ─────────────────────────────────────────────────
    "corona": FormatCategory.CORONA,
    "corona gorda": FormatCategory.CORONA,
    "petit corona": FormatCategory.PETIT_CORONA,
    "minuto": FormatCategory.PETIT_CORONA,
    "mareva": FormatCategory.PETIT_CORONA,
    "gran corona": FormatCategory.GRAN_CORONA,
    "double corona": FormatCategory.DOUBLE_CORONA,
    "prominente": FormatCategory.DOUBLE_CORONA,
    # ─── Churchill family (~180 mm × ring 47-50) ───────────────────────
    "churchill": FormatCategory.CHURCHILL,
    "double churchill": FormatCategory.CHURCHILL,
    "julieta": FormatCategory.CHURCHILL,
    # ─── Lonsdale (~165 mm × ring 42-44) ───────────────────────────────
    "lonsdale": FormatCategory.LONSDALE,
    "cervante": FormatCategory.LONSDALE,
    "cervantes": FormatCategory.LONSDALE,
    # ─── Lancero (long et fin, ~190 mm × ring 38-42) ────────────────────
    "lancero": FormatCategory.LANCERO,
    "laguito no.1": FormatCategory.LANCERO,
    "laguito n°1": FormatCategory.LANCERO,
    # ─── Panetela (élégant, ~120-170 × ring 30-38) ──────────────────────
    "panetela": FormatCategory.PANETELA,
    "panatela": FormatCategory.PANETELA,
    "small panatela": FormatCategory.PANETELA,
    "laguito no.2": FormatCategory.PANETELA,
    "laguito n°2": FormatCategory.PANETELA,
    # ─── Figurados (asymétriques) ───────────────────────────────────────
    "perfecto": FormatCategory.PERFECTO,
    "torpedo": FormatCategory.TORPEDO,
    "piramide": FormatCategory.TORPEDO,
    "pirámide": FormatCategory.TORPEDO,
    "belicoso": FormatCategory.BELICOSO,
    "campana": FormatCategory.BELICOSO,
    "figurado": FormatCategory.FIGURADO,
    "salomon": FormatCategory.FIGURADO,
    "salomones": FormatCategory.FIGURADO,
    "diadema": FormatCategory.FIGURADO,
    # ─── Petits formats ────────────────────────────────────────────────
    "demi tasse": FormatCategory.DEMI_TASSE,
    "demi-tasse": FormatCategory.DEMI_TASSE,
    "cigarito": FormatCategory.DEMI_TASSE,
    "demi-corona": FormatCategory.PETIT_CORONA,
}


def map_format_category(label: str | None) -> FormatCategory:
    if not label:
        return FormatCategory.OTHER
    key = label.strip().lower()
    if key in _FORMAT_ALIASES:
        return _FORMAT_ALIASES[key]
    # Fallback: contains-match for compound names like "Robusto Extra Long"
    for alias, cat in _FORMAT_ALIASES.items():
        if alias in key:
            return cat
    return FormatCategory.OTHER


# ---------------------------------------------------------------------------
# Strength — 1..5 → Intensity
# ---------------------------------------------------------------------------

_STRENGTH_BY_LEVEL: dict[int, Intensity] = {
    1: Intensity.MILD,
    2: Intensity.MILD_MEDIUM,
    3: Intensity.MEDIUM,
    4: Intensity.MEDIUM_FULL,
    5: Intensity.FULL,
}


def map_strength(level: int | None) -> Intensity | None:
    if level is None:
        return None
    return _STRENGTH_BY_LEVEL.get(level)


# ---------------------------------------------------------------------------
# Blend leaves — role string → BlendComponentType
# ---------------------------------------------------------------------------

_LEAF_ROLE_MAP: dict[str, BlendComponentType] = {
    "wrapper": BlendComponentType.WRAPPER,
    "binder": BlendComponentType.BINDER,
    # The merchant only labels "filler" generically (no seco/volado/ligero),
    # so we attribute everything to FILLER_SECO by default.
    "filler": BlendComponentType.FILLER_SECO,
}


def map_blend_component_type(role: str) -> BlendComponentType:
    return _LEAF_ROLE_MAP.get(role.strip().lower(), BlendComponentType.FILLER_SECO)


# ---------------------------------------------------------------------------
# Slugs
# ---------------------------------------------------------------------------


def brand_slug_from(name: str) -> str:
    return compose_slug(name)


_TRAILING_PACK_RE = __import__("re").compile(r"\s*\(\d+\)\s*$")


def strip_pack_suffix(title: str) -> str:
    """Remove the trailing "(N)" pack-size hint mistercigar appends to titles.

    "Vallejuelo Churchill (1)"  → "Vallejuelo Churchill"
    "Vallejuelo Churchill (25)" → "Vallejuelo Churchill"
    """

    return _TRAILING_PACK_RE.sub("", title).strip()


def cigar_slug_from(brand_name: str, title: str) -> str:
    """Slug of the canonical cigar — packaging-agnostic.

    Three merchant fiches "Vallejuelo Churchill (1)", "(5)" and "(25)" must
    converge to the same slug so the cigar is upserted only once.
    """

    return compose_slug(brand_name, strip_pack_suffix(title))


# ---------------------------------------------------------------------------
# Line inference from URL path
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InferredLine:
    slug: str
    name: str


def infer_line_from_url(url: str, brand_slug: str) -> InferredLine | None:
    """Return the line component from a mistercigar /boutique/... URL.

    Path shape:
        /boutique/{country}/{brand}/{line}[/{sub-line}]/{product-slug}/
    The product is always the LAST segment. The first segment after /boutique
    is a country bucket (cigares-dominicains, cigares, …) and is ignored.
    The brand position is detected by matching brand_slug. The segment
    immediately AFTER the brand (if not the product) is treated as the line.

    Returns None when the URL is too short to expose a meaningful line.
    """

    try:
        parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
    except Exception:
        return None
    if not parts or parts[0] != "boutique" or len(parts) < 3:
        return None

    taxonomic = parts[1:-1]  # drop "boutique" prefix and the trailing product slug
    if brand_slug not in taxonomic:
        return None

    bi = taxonomic.index(brand_slug)
    if bi + 1 >= len(taxonomic):
        return None

    line_slug = taxonomic[bi + 1]
    # Guard: don't treat a country bucket as a line if brand happens to come last
    if line_slug.startswith("cigares-"):
        return None

    # Build a human-readable name from the slug (capitalize each word, lowercase fillers).
    name = _humanise_slug(line_slug)
    return InferredLine(slug=line_slug, name=name)


_LOWERCASE_TOKENS = {"de", "des", "du", "et", "la", "le", "les", "a", "y", "the"}


def _humanise_slug(slug: str) -> str:
    words = slug.split("-")
    out: list[str] = []
    for i, w in enumerate(words):
        if i > 0 and w in _LOWERCASE_TOKENS:
            out.append(w)
        else:
            out.append(w.capitalize())
    return " ".join(out)


def resolve_line(url: str, brand_name: str, brand_slug: str) -> tuple[str, str]:
    """Returns (line_slug, line_name) for persistence.

    Tries the URL first; falls back to a "default" line named after the brand
    (slug=brand_slug, name=brand_name) when no taxonomic line can be detected.
    """

    inferred = infer_line_from_url(url, brand_slug)
    if inferred is not None:
        return (inferred.slug, inferred.name)
    return (brand_slug, brand_name)


# ---------------------------------------------------------------------------
# Top-level: ProductExtraction → (brand_name, cigar_kwargs, blend_components)
# ---------------------------------------------------------------------------


def build_cigar_components(
    extraction: ProductExtraction,
) -> list[BlendComponent]:
    """Build BlendComponent domain objects from an extraction (cigar_id unset)."""

    components: list[BlendComponent] = []
    for leaf in extraction.blend_leaves:
        origin_iso = map_country(leaf.origin_text)
        # Trust = MEDIUM when origin can be mapped, LOW otherwise
        confidence = Confidence.MEDIUM if origin_iso else Confidence.LOW
        components.append(
            BlendComponent(
                component_type=map_blend_component_type(leaf.role),
                tobacco_origin=origin_iso,
                source_confidence=confidence,
            )
        )
    return components


def build_cigar(
    extraction: ProductExtraction,
    *,
    line_id: object,  # UUID — typed as object to avoid uuid import here
    blend_components: list[BlendComponent] | None = None,
) -> Cigar:
    """Compose a Cigar entity from an extraction. Does NOT persist."""

    if not extraction.brand_name:
        raise ValueError(f"brand_name is required, got extraction={extraction.title!r}")

    slug = cigar_slug_from(extraction.brand_name, extraction.title)
    canonical_full_name = strip_pack_suffix(extraction.title)
    vitola = extraction.vitola_name or "Unknown"

    # weight_g exposed by the merchant is the TOTAL weight of the pack
    # (so 25× cigars in a box). The canonical Cigar.weight_g is the
    # per-cigar weight, so we divide by pack_size when known and >1.
    raw_weight = extraction.weight_g
    pack_size = extraction.pack_size
    unit_weight: Decimal | None = None
    if raw_weight is not None and pack_size and pack_size > 1:
        unit_weight = (raw_weight / Decimal(pack_size)).quantize(Decimal("0.01"))
    elif raw_weight is not None and (pack_size is None or pack_size == 1):
        unit_weight = _normalize_weight_g(raw_weight)
    # If still > 500g per cigar after normalisation, drop the value rather than
    # raising — these are usually merchant data quality issues (missing pack_size,
    # weight in mg, etc.).
    if unit_weight is not None and unit_weight > 500:
        unit_weight = None

    # Convert all blend countries into the canonical Cigar.* country fields
    wrapper_country = map_country(extraction.wrapper_origin)
    binder_country = map_country(extraction.binder_origin)
    filler_countries: list[str] = []
    for raw in extraction.filler_origins:
        iso = map_country(raw)
        if iso and iso not in filler_countries:
            filler_countries.append(iso)

    production_iso = map_country(extraction.production_country)
    is_cuban = production_iso == "CUB" or wrapper_country == "CUB"

    return Cigar(
        line_id=line_id,  # type: ignore[arg-type]
        slug=slug,
        full_name=canonical_full_name,
        vitola_name=vitola,
        format_category=map_format_category(extraction.vitola_name),
        length_mm=extraction.length_mm,
        ring_gauge=extraction.ring_gauge,
        ring_gauge_mm=extraction.ring_gauge_mm,
        weight_g=unit_weight,
        wrapper_country=wrapper_country,
        binder_country=binder_country,
        filler_countries=filler_countries,
        strength=map_strength(extraction.strength_level),
        body=map_strength(extraction.strength_level),
        is_cuban=is_cuban,
        is_handmade=True,
        blend_components=blend_components or [],
    )


def _normalize_weight_g(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    # Some merchant fields report weight as kg already converted; cap obvious noise
    return value.quantize(Decimal("0.01"))
