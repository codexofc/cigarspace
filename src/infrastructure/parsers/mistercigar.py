# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""HTML parsers for mistercigar.com (WordPress + WooCommerce + theme Flatsome).

Two parsers:
- MistercigarListingParser : extracts product URLs + next-page URL from a
  category listing such as /categorie-produit/cigares/cigares-a-lunite/
- MistercigarProductParser : extracts a ProductExtraction from a product
  detail page (e.g. /boutique/cigares/cigares-a-lunite/<slug>-1/)

Both parsers rely on `selectolax` (lexbor backend) for raw speed. Selectors
were derived from inspection of real pages saved under tests/fixtures.

Two structured-data sources are exploited on the detail page:
- the WooCommerce attributes table  → 15 typed key/value pairs
- the JSON-LD Product block (inside an @graph) → price, image, SKU
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urljoin, urlparse

from selectolax.parser import HTMLParser, Node

from application.ports.parser import (
    BlendLeafExtraction,
    ListingExtraction,
    ProductExtraction,
)
from infrastructure.observability.logging import get_logger

_log = get_logger("parser.mistercigar")

# Slug pattern of a product URL: ends with "-<digits>/" (the WooCommerce trailing id)
_PRODUCT_URL_RE = re.compile(r"^https://mistercigar\.com/boutique/[^?#]+/[a-z0-9-]+-\d+/$")

# Matches /page/<n>/ at the end of a category URL
_PAGE_IN_URL_RE = re.compile(r"/page/(\d+)/?$")


def next_page_url(tree: HTMLParser, page_url: str) -> str | None:
    """Locate the link to the next category page.

    Strategy:
      1. find the <span class="page-number current"> to read the current N
         (fall back to inferring N from the URL's /page/N/ suffix, or N=1)
      2. find an <a class="page-number" href=".../page/N+1/"> in the
         pagination nav (Flatsome strips the .next class so we can't rely
         on a CSS selector alone)
    """

    # Detect current page number
    current = 1
    cur_node = tree.css_first("span.page-number.current") or tree.css_first("span.current")
    if cur_node is not None:
        text = (cur_node.text() or "").strip()
        if text.isdigit():
            current = int(text)
    else:
        m = _PAGE_IN_URL_RE.search(page_url)
        if m:
            current = int(m.group(1))

    target = current + 1

    for a in tree.css("a.page-number, a.page-numbers"):
        text = (a.text() or "").strip()
        if text.isdigit() and int(text) == target:
            href = a.attributes.get("href")
            if href:
                return urljoin(page_url, href)
    return None


# Selectolax helpers ---------------------------------------------------------


def _text(node: Node | None) -> str | None:
    if node is None:
        return None
    t = node.text(strip=True)
    return t or None


def _to_decimal(s: str | None) -> Decimal | None:
    if not s:
        return None
    s = s.replace(",", ".").strip()
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _to_int(s: str | None) -> int | None:
    if not s:
        return None
    digits = re.search(r"\d+", s)
    return int(digits.group(0)) if digits else None


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


class MistercigarListingParser:
    """Pulls product URLs + the next-page URL out of a WooCommerce category page."""

    def parse_listing(self, *, html: str, page_url: str) -> ListingExtraction:
        tree = HTMLParser(html)
        product_urls: list[str] = []
        seen: set[str] = set()

        # WooCommerce/Flatsome lists products inside .products with <a class="woocommerce-LoopProduct-link">,
        # but we also accept any <a href> that matches the product URL regex anywhere
        # in <main> — more resilient to theme changes.
        for a in tree.css("a[href]"):
            href = a.attributes.get("href")
            if not href:
                continue
            absolute = urljoin(page_url, href)
            if _PRODUCT_URL_RE.match(absolute) and absolute not in seen:
                seen.add(absolute)
                product_urls.append(absolute)

        # Pagination — mistercigar's Flatsome theme renders:
        #   <span class="page-number current">N</span>
        #   <a class="page-number" href=".../page/N+1/">N+1</a>
        # ...without the .next class. We compute next by finding the current
        # page number then picking the link whose text == current+1.
        next_url: str | None = next_page_url(tree, page_url)

        _log.info(
            "listing_parsed",
            page_url=page_url,
            products=len(product_urls),
            has_next=next_url is not None,
        )
        return ListingExtraction(product_urls=product_urls, next_page_url=next_url)


# ---------------------------------------------------------------------------
# Product detail
# ---------------------------------------------------------------------------

# Mapping merchant strength symbols → 1..5 level
# "● ● ● ● ○" → 4 filled bullets out of 5
_FILLED_BULLET = "●"


def _parse_strength_bullets(text: str) -> int | None:
    if not text:
        return None
    return text.count(_FILLED_BULLET) or None


class MistercigarProductParser:
    """Extracts a ProductExtraction from a mistercigar product detail page."""

    def parse_product(self, *, html: str, page_url: str) -> ProductExtraction:
        tree = HTMLParser(html)
        domain = (urlparse(page_url).hostname or "").lower()

        title = _text(tree.css_first("h1.product_title")) or _text(
            tree.css_first("h1.product-title")
        )
        if not title:
            raise ValueError(f"product title not found at {page_url}")

        sku = _text(tree.css_first("span.sku"))

        attrs = self._parse_attributes_table(tree)
        jsonld = self._parse_jsonld_product(tree)

        # Compose blend leaves from the attribute table
        blend_leaves: list[BlendLeafExtraction] = []
        wrapper_origin = attrs.get("Feuille de cape")
        binder_origin = attrs.get("Sous-cape(s)") or attrs.get("Sous-cape")
        filler_text = attrs.get("Tripe(s)") or attrs.get("Tripe")
        if wrapper_origin:
            blend_leaves.append(BlendLeafExtraction(role="wrapper", origin_text=wrapper_origin))
        if binder_origin:
            blend_leaves.append(BlendLeafExtraction(role="binder", origin_text=binder_origin))
        filler_origins: list[str] = []
        if filler_text:
            for piece in re.split(r"[,;/]", filler_text):
                piece = piece.strip()
                if piece:
                    filler_origins.append(piece)
                    blend_leaves.append(BlendLeafExtraction(role="filler", origin_text=piece))

        weight_g: Decimal | None = None
        if (raw := attrs.get("Poids")) is not None:
            m = re.search(r"([\d.,]+)\s*(g|kg)", raw, flags=re.IGNORECASE)
            if m:
                value = _to_decimal(m.group(1))
                if value is not None:
                    weight_g = value * 1000 if m.group(2).lower() == "kg" else value

        # pack_size — comes from the "Packing" WC attribute, or from the
        # trailing "(N)" in the product title when the attribute is absent.
        pack_size = _to_int(attrs.get("Packing"))
        if pack_size is None:
            m_title = re.search(r"\((\d+)\)\s*$", title)
            if m_title:
                pack_size = int(m_title.group(1))

        # Price + image come from JSON-LD when available
        price_amount: Decimal | None = None
        price_currency: str | None = None
        primary_image_url: str | None = None
        jsonld_sku: str | None = None
        if jsonld is not None:
            primary_image_url = self._coerce_image(jsonld.get("image"))
            jsonld_sku = jsonld.get("sku")
            offers = jsonld.get("offers")
            offer = offers[0] if isinstance(offers, list) and offers else offers
            if isinstance(offer, dict):
                price_currency = offer.get("priceCurrency") or price_currency
                price_amount = _to_decimal(offer.get("price"))
                spec = offer.get("priceSpecification")
                spec = spec[0] if isinstance(spec, list) and spec else spec
                if isinstance(spec, dict):
                    price_amount = _to_decimal(spec.get("price")) or price_amount
                    price_currency = spec.get("priceCurrency") or price_currency

        return ProductExtraction(
            source_url=page_url,
            source_domain=domain,
            title=title,
            sku=sku or jsonld_sku,
            brand_name=attrs.get("Marque"),
            manufacturer=attrs.get("Fabricant"),
            vitola_name=attrs.get("Module"),
            length_mm=_to_decimal(attrs.get("Longueur (mm)")),
            ring_gauge=_to_int(attrs.get("Bague")),
            ring_gauge_mm=_to_decimal(attrs.get("Diamètre (mm)")),
            weight_g=weight_g,
            wrapper_origin=wrapper_origin,
            binder_origin=binder_origin,
            filler_origins=filler_origins,
            production_country=attrs.get("Pays de Production"),
            terroir=attrs.get("Pays / Terroir"),
            strength_text=attrs.get("Puissance"),
            strength_level=_parse_strength_bullets(attrs.get("Puissance") or ""),
            duration_text=attrs.get("Durée"),
            pack_size=pack_size,
            price_amount=price_amount,
            price_currency=price_currency,
            primary_image_url=primary_image_url,
            blend_leaves=blend_leaves,
            raw_attributes=attrs,
        )

    @staticmethod
    def _parse_attributes_table(tree: HTMLParser) -> dict[str, str]:
        table = tree.css_first(
            "table.woocommerce-product-attributes.shop_attributes"
        ) or tree.css_first("table.shop_attributes")
        if table is None:
            return {}
        rows: dict[str, str] = {}
        for tr in table.css("tr"):
            label_node = tr.css_first(
                "th.woocommerce-product-attributes-item__label"
            ) or tr.css_first("th")
            value_node = tr.css_first(
                "td.woocommerce-product-attributes-item__value"
            ) or tr.css_first("td")
            label = _text(label_node)
            value = _text(value_node)
            if label and value:
                # Decode common HTML entities the lexbor parser may leave intact
                # in text() output, then collapse whitespace.
                value = re.sub(r"\s+", " ", value).strip()
                rows[label] = value
        return rows

    @staticmethod
    def _parse_jsonld_product(tree: HTMLParser) -> dict[str, Any] | None:
        """Find the Product node, handling top-level Product or @graph wrappers."""
        for script in tree.css("script[type='application/ld+json']"):
            raw = script.text() or ""
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            candidates: list[Any] = []
            if isinstance(data, dict):
                candidates.append(data)
                if "@graph" in data and isinstance(data["@graph"], list):
                    candidates.extend(data["@graph"])
            elif isinstance(data, list):
                candidates.extend(data)
            for c in candidates:
                if isinstance(c, dict) and c.get("@type") == "Product":
                    return c
        return None

    @staticmethod
    def _coerce_image(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value:
            first = value[0]
            return first if isinstance(first, str) else None
        if isinstance(value, dict):
            return value.get("url") or value.get("@id")
        return None
