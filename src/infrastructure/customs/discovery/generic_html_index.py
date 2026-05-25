# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Generic HTML index discovery — driven by config_json.

Used as a fallback / plan B for sources whose index doesn't fit a
custom adapter. The operator describes the CSS shape in `config_json`:

    {
      "item_selector": "div.publication-entry",
      "link_selector": "a.download-pdf",
      "reference_selector": "span.ref",
      "reference_attr": null,                  # or "data-ref"
      "date_selector": "time",
      "date_attr": "datetime",                 # ISO 8601 → date
      "date_locale": "fr"                      # "fr" or "iso"
    }

Returns one DiscoveredPublication per matched item.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any, ClassVar
from urllib.parse import urljoin

from selectolax.parser import HTMLParser, Node

from application.ports.customs_discovery import (
    DiscoveredPublication,
)
from infrastructure.customs._date_fr import parse_french_date


def _node_value(node: Node | None, attr: str | None) -> str | None:
    if node is None:
        return None
    if attr:
        return node.attributes.get(attr)
    return (node.text() or "").strip() or None


def _parse_date(value: str | None, locale: str) -> date | None:
    if not value:
        return None
    if locale == "fr":
        return parse_french_date(value)
    # ISO 8601 by default
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


class GenericHtmlIndexDiscovery:
    name: ClassVar[str] = "generic-html-index"

    async def find_publications(
        self,
        *,
        index_html: str,
        index_url: str,
        config: dict[str, Any],
    ) -> Sequence[DiscoveredPublication]:
        item_selector = config.get("item_selector")
        link_selector = config.get("link_selector", "a")
        ref_selector = config.get("reference_selector")
        ref_attr = config.get("reference_attr")
        date_selector = config.get("date_selector")
        date_attr = config.get("date_attr")
        date_locale = config.get("date_locale", "iso")
        mime = config.get("document_mime", "text/html")

        if not item_selector:
            return []

        tree = HTMLParser(index_html)
        out: list[DiscoveredPublication] = []
        for item in tree.css(item_selector):
            link = item.css_first(link_selector)
            if link is None:
                continue
            href = link.attributes.get("href")
            if not href:
                continue
            absolute = urljoin(index_url, href)

            ref_node = item.css_first(ref_selector) if ref_selector else link
            reference = _node_value(ref_node, ref_attr) or absolute

            date_node = item.css_first(date_selector) if date_selector else None
            pub_date_value = _node_value(date_node, date_attr)
            pub_date = _parse_date(pub_date_value, date_locale)

            out.append(
                DiscoveredPublication(
                    regulator_reference=reference,
                    document_url=absolute,
                    publication_date=pub_date,
                    effective_date=None,
                    document_mime=mime,
                )
            )
        return out
