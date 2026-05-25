# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Discovery adapter for the DGDDI Open Data landing page (FR).

The DGDDI publishes one ODS spreadsheet per JORF arrêté under
``douane.gouv.fr/sites/default/files/.../Maquette JORF <date>.ods``.

Since 2024 the JORF arrêté itself no longer carries the price table — it
simply names this portal as the authoritative source. We therefore use this
page as our primary FR discovery channel.

Synthetic regulator_reference: ``FR-DOUANE-YYYY-MM-DD`` keyed on the
effective date parsed out of the filename. Stable across runs and unique
per arrêté.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from typing import Any, ClassVar
from urllib.parse import unquote, urljoin

from selectolax.parser import HTMLParser

from application.ports.customs_discovery import (
    DiscoveredPublication,
    ICustomsDiscoveryAdapter,
)
from infrastructure.customs._date_fr import parse_french_date


# "Maquette JORF 1er juin 2026.ods" / "Maquette JORF 1er février 2026.ods"
_FILENAME_DATE_RE = re.compile(
    r"Maquette\s+JORF\s+(\d{1,2}(?:er|ᵉʳ)?\s+[A-Za-zéûôîà]+\s+\d{4})",
    re.IGNORECASE,
)


class DouaneOpenDataDiscovery:
    name: ClassVar[str] = "douane-opendata"

    async def find_publications(
        self,
        *,
        index_html: str,
        index_url: str,
        config: dict[str, Any],
    ) -> Sequence[DiscoveredPublication]:
        prefer_ext = (config.get("prefer_extension") or "ods").lower()
        tree = HTMLParser(index_html)
        seen: dict[str, DiscoveredPublication] = {}

        for a in tree.css("a[href]"):
            href = a.attributes.get("href") or ""
            href_lower = href.lower()
            if not href_lower.endswith(f".{prefer_ext}"):
                continue

            # Decode for filename parsing; keep raw href for URL build.
            filename = unquote(href.rsplit("/", 1)[-1])
            m = _FILENAME_DATE_RE.search(filename)
            if not m:
                continue
            eff = parse_french_date(m.group(1))
            if eff is None:
                continue

            ref = f"FR-DOUANE-{eff.isoformat()}"
            if ref in seen:
                continue

            absolute = urljoin(index_url, href)
            seen[ref] = DiscoveredPublication(
                regulator_reference=ref,
                document_url=absolute,
                publication_date=_publication_date_from_url(href, eff),
                effective_date=eff,
                document_mime=_mime_for_ext(prefer_ext),
            )

        return list(seen.values())


def _publication_date_from_url(href: str, fallback: date) -> date:
    """Files live under /sites/default/files/YYYY-MM/DD/... — that path
    encodes the upload date (close enough to "publication on the portal")."""
    m = re.search(r"/files/(\d{4})-(\d{2})/(\d{1,2})/", href)
    if not m:
        return fallback
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return fallback


def _mime_for_ext(ext: str) -> str:
    return {
        "ods": "application/vnd.oasis.opendocument.spreadsheet",
        "pdf": "application/pdf",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(ext, "application/octet-stream")
