# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from application.ports.parser import BlendLeafExtraction, ProductExtraction
from application.services.extraction_mapping import (
    brand_slug_from,
    build_cigar,
    build_cigar_components,
    infer_line_from_url,
    map_blend_component_type,
    map_country,
    map_format_category,
    map_strength,
    resolve_line,
)
from domain.enums import BlendComponentType, FormatCategory, Intensity


def test_map_country_aliases() -> None:
    assert map_country("République dominicaine") == "DOM"
    assert map_country("RÉPUBLIQUE DOMINICAINE") == "DOM"
    assert map_country("république dominicaine") == "DOM"
    assert map_country("Nicaragua") == "NIC"
    assert map_country("Équateur") == "ECU"
    assert map_country("Cuba") == "CUB"
    assert map_country("Honduras") == "HND"


def test_map_country_unknown_returns_none() -> None:
    assert map_country(None) is None
    assert map_country("") is None
    assert map_country("Atlantide") is None


def test_map_format_category() -> None:
    assert map_format_category("Churchill") is FormatCategory.CHURCHILL
    assert map_format_category("Robusto") is FormatCategory.ROBUSTO
    assert map_format_category("ROBUSTO") is FormatCategory.ROBUSTO
    assert map_format_category("Gordo") is FormatCategory.TORO
    assert map_format_category(None) is FormatCategory.OTHER
    assert map_format_category("Inventé") is FormatCategory.OTHER


def test_map_format_category_extended() -> None:
    # The expanded alias table (Améliro 1)
    assert map_format_category("Robusto Gordo") is FormatCategory.ROBUSTO
    assert map_format_category("Double Gordo") is FormatCategory.TORO
    assert map_format_category("Petit Robusto") is FormatCategory.ROBUSTO
    assert map_format_category("Magnum") is FormatCategory.TORO
    assert map_format_category("Pirámide") is FormatCategory.TORPEDO
    assert map_format_category("Salomon") is FormatCategory.FIGURADO
    assert map_format_category("Laguito No.1") is FormatCategory.LANCERO


def test_map_format_category_fallback_on_substring() -> None:
    # Compound or noisy names still fall onto a parent category
    assert map_format_category("Robusto Extra Long") is FormatCategory.ROBUSTO
    assert map_format_category("Toro Especial 2024") is FormatCategory.TORO


# ---- Line inference from URL -----------------------------------------------


def test_infer_line_from_url_with_line_segment() -> None:
    url = (
        "https://mistercigar.com/boutique/cigares-dominicains/la-couronne/"
        "seleccion-privada/la-couronne-seleccion-privada-magnum-aa-1/"
    )
    line = infer_line_from_url(url, brand_slug="la-couronne")
    assert line is not None
    assert line.slug == "seleccion-privada"
    assert line.name == "Seleccion Privada"


def test_infer_line_returns_none_when_no_line_segment() -> None:
    # Vallejuelo Churchill sits directly under cigares-a-lunite — no line
    url = "https://mistercigar.com/boutique/cigares/cigares-a-lunite/vallejuelo-churchill-1/"
    assert infer_line_from_url(url, brand_slug="vallejuelo") is None


def test_resolve_line_falls_back_to_brand() -> None:
    url = "https://mistercigar.com/boutique/cigares/cigares-a-lunite/vallejuelo-churchill-1/"
    slug, name = resolve_line(url, brand_name="Vallejuelo", brand_slug="vallejuelo")
    assert slug == "vallejuelo"
    assert name == "Vallejuelo"


def test_resolve_line_uses_inferred_when_available() -> None:
    url = (
        "https://mistercigar.com/boutique/cigares-dominicains/la-couronne/"
        "gran-reserva/la-couronne-gran-reserva-mostros-1/"
    )
    slug, name = resolve_line(url, brand_name="La Couronne", brand_slug="la-couronne")
    assert slug == "gran-reserva"
    assert name == "Gran Reserva"


def test_map_strength() -> None:
    assert map_strength(1) is Intensity.MILD
    assert map_strength(3) is Intensity.MEDIUM
    assert map_strength(5) is Intensity.FULL
    assert map_strength(None) is None
    assert map_strength(99) is None


def test_map_blend_component_type() -> None:
    assert map_blend_component_type("wrapper") is BlendComponentType.WRAPPER
    assert map_blend_component_type("binder") is BlendComponentType.BINDER
    assert map_blend_component_type("filler") is BlendComponentType.FILLER_SECO
    assert map_blend_component_type("unknown") is BlendComponentType.FILLER_SECO


def test_brand_slug_from_normalises_accents_and_spaces() -> None:
    assert brand_slug_from("Vallejuelo") == "vallejuelo"
    assert brand_slug_from("Arturo Fuente") == "arturo-fuente"
    assert brand_slug_from("Padrón") == "padron"


def _sample_extraction() -> ProductExtraction:
    return ProductExtraction(
        source_url="https://mistercigar.com/boutique/x/vallejuelo-churchill-1/",
        source_domain="mistercigar.com",
        title="Vallejuelo Churchill (1)",
        sku="CIGDO01VANO001C",
        brand_name="Vallejuelo",
        manufacturer="Tabacalera Privada",
        vitola_name="Churchill",
        length_mm=Decimal("178"),
        ring_gauge=47,
        ring_gauge_mm=Decimal("18.7"),
        weight_g=Decimal("21"),
        wrapper_origin="Équateur",
        binder_origin="République dominicaine",
        filler_origins=["Nicaragua", "République dominicaine"],
        production_country="République dominicaine",
        strength_text="● ● ● ● ○",
        strength_level=4,
        blend_leaves=[
            BlendLeafExtraction(role="wrapper", origin_text="Équateur"),
            BlendLeafExtraction(role="binder", origin_text="République dominicaine"),
            BlendLeafExtraction(role="filler", origin_text="Nicaragua"),
            BlendLeafExtraction(role="filler", origin_text="République dominicaine"),
        ],
    )


def test_build_cigar_components_maps_origins_and_confidence() -> None:
    components = build_cigar_components(_sample_extraction())
    assert len(components) == 4
    assert components[0].component_type is BlendComponentType.WRAPPER
    assert components[0].tobacco_origin == "ECU"
    assert components[1].tobacco_origin == "DOM"
    assert components[2].component_type is BlendComponentType.FILLER_SECO
    assert components[2].tobacco_origin == "NIC"


def test_build_cigar_full_mapping() -> None:
    line_id = uuid4()
    components = build_cigar_components(_sample_extraction())
    cigar = build_cigar(_sample_extraction(), line_id=line_id, blend_components=components)

    assert cigar.line_id == line_id
    assert cigar.slug == "vallejuelo-vallejuelo-churchill"
    assert cigar.full_name == "Vallejuelo Churchill"
    assert cigar.vitola_name == "Churchill"
    assert cigar.format_category is FormatCategory.CHURCHILL
    assert cigar.length_mm == Decimal("178")
    assert cigar.ring_gauge == 47
    assert cigar.ring_gauge_mm == Decimal("18.7")
    assert cigar.weight_g == Decimal("21.00")
    assert cigar.wrapper_country == "ECU"
    assert cigar.binder_country == "DOM"
    assert set(cigar.filler_countries) == {"NIC", "DOM"}
    assert cigar.strength is Intensity.MEDIUM_FULL
    assert cigar.is_cuban is False
    assert cigar.is_handmade is True
    assert len(cigar.blend_components) == 4
