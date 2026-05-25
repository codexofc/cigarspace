# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from infrastructure.parsers.mistercigar import (
    MistercigarListingParser,
    MistercigarProductParser,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"
LISTING_URL = "https://mistercigar.com/categorie-produit/cigares/cigares-a-lunite/"
DETAIL_URL = "https://mistercigar.com/boutique/cigares/cigares-a-lunite/vallejuelo-churchill-1/"


@pytest.fixture(scope="session")
def listing_html() -> str:
    return (FIXTURES / "mistercigar_listing.html").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def detail_html() -> str:
    return (FIXTURES / "mistercigar_detail.html").read_text(encoding="utf-8")


# ---- Listing parser --------------------------------------------------------


def test_listing_extracts_product_urls(listing_html: str) -> None:
    result = MistercigarListingParser().parse_listing(html=listing_html, page_url=LISTING_URL)
    assert len(result.product_urls) >= 20  # 24 on the captured page
    assert all(u.startswith("https://mistercigar.com/boutique/") for u in result.product_urls)
    # Every URL ends with -<digits>/ (WooCommerce product slug pattern)
    for u in result.product_urls:
        assert u.rstrip("/").rsplit("-", 1)[-1].isdigit(), u


def test_listing_deduplicates(listing_html: str) -> None:
    result = MistercigarListingParser().parse_listing(html=listing_html, page_url=LISTING_URL)
    assert len(result.product_urls) == len(set(result.product_urls))


# ---- Product parser --------------------------------------------------------


def test_product_extracts_core_fields(detail_html: str) -> None:
    p = MistercigarProductParser().parse_product(html=detail_html, page_url=DETAIL_URL)

    assert p.title == "Vallejuelo Churchill (1)"
    assert p.sku == "CIGDO01VANO001C"
    assert p.brand_name == "Vallejuelo"
    assert p.manufacturer == "Tabacalera Privada"
    assert p.vitola_name == "Churchill"


def test_product_extracts_dimensions(detail_html: str) -> None:
    p = MistercigarProductParser().parse_product(html=detail_html, page_url=DETAIL_URL)

    assert p.length_mm == Decimal("178")
    assert p.ring_gauge == 47
    assert p.ring_gauge_mm == Decimal("18.7")
    # 0.021 kg → 21 g (we normalize kg → g internally)
    assert p.weight_g == Decimal("21.000")


def test_product_extracts_blend(detail_html: str) -> None:
    p = MistercigarProductParser().parse_product(html=detail_html, page_url=DETAIL_URL)

    assert p.wrapper_origin == "Équateur"
    assert p.binder_origin == "République dominicaine"
    assert p.filler_origins == ["Nicaragua", "République dominicaine"]
    roles = [leaf.role for leaf in p.blend_leaves]
    assert roles.count("wrapper") == 1
    assert roles.count("binder") == 1
    assert roles.count("filler") == 2


def test_product_extracts_sensorial(detail_html: str) -> None:
    p = MistercigarProductParser().parse_product(html=detail_html, page_url=DETAIL_URL)

    assert p.strength_text == "● ● ● ● ○"
    assert p.strength_level == 4
    assert "80" in (p.duration_text or "")


def test_product_extracts_pricing_and_media(detail_html: str) -> None:
    p = MistercigarProductParser().parse_product(html=detail_html, page_url=DETAIL_URL)

    assert p.price_amount == Decimal("13.00")
    assert p.price_currency == "CHF"
    assert p.primary_image_url is not None
    assert p.primary_image_url.startswith("https://mistercigar.com/wp-content/uploads/")
    assert p.primary_image_url.endswith((".jpg", ".jpeg", ".png", ".webp"))


def test_product_raises_when_title_missing() -> None:
    bare_html = "<html><body><p>no product here</p></body></html>"
    with pytest.raises(ValueError):
        MistercigarProductParser().parse_product(html=bare_html, page_url=DETAIL_URL)
