# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""HTML parsers for cigarpassion.ch (WooCommerce + WoodMart theme).

Two parsers:
- CigarpassionListingParser : sitemap-driven. The category pages are
  JS-rendered (the WoodMart theme injects products dynamically) so we
  bypass them entirely and parse the WordPress XML product sitemaps,
  which list every product URL. Three sitemaps (1, 2, 3) chained via
  ``next_page_url``.
- CigarpassionProductParser : extracts a ProductExtraction from a
  product detail page. The DOM is the same WooCommerce flavour as
  mistercigar.com (``table.shop_attributes`` with the same French
  labels), so the heavy lifting is shared logic. Currency is CHF.

Both parsers rely on ``selectolax`` (lexbor) plus a tiny regex for the
sitemap XML.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin, urlparse

from selectolax.parser import HTMLParser

from application.ports.parser import (
    BlendLeafExtraction,
    ListingExtraction,
    ProductExtraction,
)
from infrastructure.observability.logging import get_logger


_log = get_logger("parser.cigarpassion")

# Only follow product URLs that look like cigars; skip humidors, alcohols,
# accessories, pipe tobacco, etc. listed in the same sitemaps.
# Cigars live under either /boutique/cigares/, /boutique/cigares-<origin>/
# (e.g. /boutique/cigares-cubains/...) or the same shape under the
# /categorie-produit/ alias.
_CIGAR_URL_RE = re.compile(
    r"^https?://cigarpassion\.ch/"
    r"(?:boutique|categorie-produit)"
    r"/cigares(?:-[a-z]+)?/",
    flags=re.IGNORECASE,
)

# Matches the sitemap-index suffix product-sitemap{N}.xml
_SITEMAP_INDEX_RE = re.compile(r"product-sitemap(\d+)\.xml$", flags=re.IGNORECASE)


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


class CigarpassionListingParser:
    """Reads product URLs out of a cigarpassion WordPress XML sitemap."""

    def parse_listing(self, *, html: str, page_url: str) -> ListingExtraction:
        urls = re.findall(r"<loc>([^<]+)</loc>", html)
        product_urls: list[str] = []
        seen: set[str] = set()
        for raw in urls:
            url = raw.strip()
            if not _CIGAR_URL_RE.match(url):
                continue
            if url in seen:
                continue
            seen.add(url)
            product_urls.append(url)

        next_url: str | None = None
        m = _SITEMAP_INDEX_RE.search(page_url)
        if m:
            current = int(m.group(1))
            candidate = re.sub(
                _SITEMAP_INDEX_RE,
                f"product-sitemap{current + 1}.xml",
                page_url,
            )
            # We can't probe the URL here (no fetcher), so we always offer
            # the next-numbered sitemap; the crawl_listing_job stops when
            # the fetcher returns nothing useful or when max_pages is hit.
            # Cap at 5 to bound the walk in case of future numbering drift.
            if current < 5:
                next_url = candidate

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


def _text(node) -> str | None:
    if node is None:
        return None
    text = node.text() or ""
    return text.strip() or None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Strip currency / spaces and convert comma decimals
    s = re.sub(r"[^0-9,.\-]", "", s).replace(",", ".")
    if not s or s in {".", "-"}:
        return None
    try:
        return Decimal(s)
    except Exception:  # noqa: BLE001
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    digits = re.search(r"\d+", str(value))
    return int(digits.group(0)) if digits else None


_PRICE_RE = re.compile(r"([A-Z]{3})?\s*([0-9]+[\.,]?[0-9]*)", flags=re.IGNORECASE)


def _parse_price_with_currency(text: str) -> tuple[Decimal | None, str | None]:
    if not text:
        return None, None
    # cigarpassion renders "CHF13.00" or "CHF 13.00" or "CHF13.00 - CHF200.00"
    first_chunk = text.split("-")[0]
    m = _PRICE_RE.search(first_chunk)
    if not m:
        return None, None
    code = (m.group(1) or "").upper() or None
    amount = _to_decimal(m.group(2))
    return amount, code


class CigarpassionProductParser:
    """Extracts a ProductExtraction from a cigarpassion product detail page."""

    def parse_product(self, *, html: str, page_url: str) -> ProductExtraction:
        tree = HTMLParser(html)
        domain = (urlparse(page_url).hostname or "").lower()

        title = _text(tree.css_first("h1.product_title")) or _text(tree.css_first("h1"))
        if not title:
            raise ValueError(f"product title not found at {page_url}")

        sku = _text(tree.css_first("span.sku"))

        attrs = self._parse_attributes_table(tree)
        jsonld = self._parse_jsonld_product(tree)

        # Blend leaves derived from the attributes table (same French labels
        # as mistercigar — both run the same WooCommerce attribute taxonomy).
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

        pack_size = _to_int(attrs.get("Packing"))
        if pack_size is None:
            m_title = re.search(r"\((\d+)\)\s*$", title)
            if m_title:
                pack_size = int(m_title.group(1))

        # Price — JSON-LD when available, else parse the rendered ``p.price``
        # (e.g. ``CHF13.00``).
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

        if price_amount is None:
            price_text = _text(tree.css_first("p.price")) or _text(tree.css_first(".price"))
            if price_text:
                amount, code = _parse_price_with_currency(price_text)
                price_amount = price_amount or amount
                price_currency = price_currency or code

        # Fallback main image if JSON-LD didn't carry one.
        if primary_image_url is None:
            img = tree.css_first("div.product img.wp-post-image") or tree.css_first(
                ".woocommerce-product-gallery__image img"
            )
            if img is not None:
                primary_image_url = (
                    img.attributes.get("src")
                    or img.attributes.get("data-src")
                    or img.attributes.get("data-large_image")
                )

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
            strength_level=None,
            duration_text=attrs.get("Durée"),
            pack_size=pack_size,
            price_amount=price_amount,
            price_currency=price_currency or "CHF",  # default for this shop
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
                value = re.sub(r"\s+", " ", value).strip()
                rows[label] = value
        return rows

    @staticmethod
    def _parse_jsonld_product(tree: HTMLParser) -> dict[str, Any] | None:
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
