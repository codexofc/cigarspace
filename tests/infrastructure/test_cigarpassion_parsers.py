# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Unit tests for the cigarpassion.ch parsers + parser registry dispatch."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from infrastructure.parsers import (
    UnknownDomainError,
    listing_parser_for_url,
    pair_for_url,
    product_parser_for_url,
)
from infrastructure.parsers.cigarpassion import (
    CigarpassionListingParser,
    CigarpassionProductParser,
)


_FIXTURES = Path(__file__).parent.parent / "fixtures" / "cigarpassion"


def _load(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def test_listing_keeps_only_cigar_urls() -> None:
    parser = CigarpassionListingParser()
    res = parser.parse_listing(
        html=_load("product-sitemap1.xml"),
        page_url="https://cigarpassion.ch/product-sitemap1.xml",
    )
    # 3 cigar URLs out of 6 (humidor / armagnac / lighter excluded).
    assert len(res.product_urls) == 3
    assert all("cigar" in u.lower() or "vallejuelo" in u.lower() for u in res.product_urls)


def test_listing_links_next_sitemap() -> None:
    parser = CigarpassionListingParser()
    res = parser.parse_listing(
        html=_load("product-sitemap1.xml"),
        page_url="https://cigarpassion.ch/product-sitemap1.xml",
    )
    assert res.next_page_url == "https://cigarpassion.ch/product-sitemap2.xml"


def test_listing_stops_after_sitemap_5() -> None:
    parser = CigarpassionListingParser()
    res = parser.parse_listing(
        html="<urlset/>",
        page_url="https://cigarpassion.ch/product-sitemap5.xml",
    )
    assert res.next_page_url is None


# ---------------------------------------------------------------------------
# Product detail
# ---------------------------------------------------------------------------


def test_product_extracts_core_fields() -> None:
    parser = CigarpassionProductParser()
    page = parser.parse_product(
        html=_load("vallejuelo-churchill-1.html"),
        page_url=(
            "https://cigarpassion.ch/boutique/cigares/cigares-a-lunite/vallejuelo-churchill-1/"
        ),
    )
    assert page.title.startswith("Vallejuelo Churchill")
    assert page.brand_name == "Vallejuelo"
    assert page.manufacturer == "Tabacalera Privada"
    assert page.vitola_name == "Churchill"
    assert page.length_mm == Decimal("178")
    assert page.ring_gauge_mm == Decimal("18.7")
    assert page.weight_g == Decimal("21.000")  # 0.021 kg → 21 g
    assert page.pack_size == 1


def test_product_parses_price_in_chf() -> None:
    parser = CigarpassionProductParser()
    page = parser.parse_product(
        html=_load("vallejuelo-churchill-1.html"),
        page_url="https://cigarpassion.ch/boutique/cigares/cigares-a-lunite/x/",
    )
    assert page.price_amount == Decimal("13.00")
    assert page.price_currency == "CHF"


def test_product_blend_leaves() -> None:
    parser = CigarpassionProductParser()
    page = parser.parse_product(
        html=_load("vallejuelo-churchill-1.html"),
        page_url="https://cigarpassion.ch/boutique/cigares/cigares-a-lunite/x/",
    )
    roles = [leaf.role for leaf in page.blend_leaves]
    assert "wrapper" in roles
    assert "binder" in roles
    assert roles.count("filler") == 2  # Nicaragua + République dominicaine


# ---------------------------------------------------------------------------
# Registry dispatch
# ---------------------------------------------------------------------------


def test_registry_picks_mistercigar() -> None:
    pair = pair_for_url("https://mistercigar.com/boutique/foo/bar-1/")
    assert pair.name == "mistercigar"


def test_registry_picks_cigarpassion() -> None:
    pair = pair_for_url(
        "https://cigarpassion.ch/boutique/cigares-cubains/cohiba/cohiba-behike-bhk-52/"
    )
    assert pair.name == "cigarpassion"


def test_registry_strips_www() -> None:
    pair = pair_for_url("https://www.cigarpassion.ch/boutique/cigares/x/")
    assert pair.name == "cigarpassion"


def test_registry_raises_on_unknown_domain() -> None:
    with pytest.raises(UnknownDomainError):
        pair_for_url("https://random.example/product/abc/")


def test_dispatch_helpers_return_callable_parsers() -> None:
    listing = listing_parser_for_url("https://cigarpassion.ch/product-sitemap1.xml")
    product = product_parser_for_url("https://cigarpassion.ch/boutique/cigares/x-1/")
    assert hasattr(listing, "parse_listing")
    assert hasattr(product, "parse_product")
