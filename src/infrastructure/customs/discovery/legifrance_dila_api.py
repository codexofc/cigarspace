# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Discovery via the DILA Légifrance JSON API (PISTE-gated).

Why not scrape Légifrance HTML? Their WAF returns 403 even to TLS-impersonating
clients in some windows. The official JSON API on PISTE is rock-solid and free
after registration.

Endpoint:
  POST {api_base_url}/search
  body: {
    "fond": "JORF",
    "recherche": {
      "champs": [
        {"typeChamp": "TEXTE", "criteres": [
          {"typeRecherche": "EXACTE", "valeur": "homologation prix tabac"}
        ]}
      ],
      "filtres": [],
      "operateur": "ET",
      "pageNumber": 1,
      "pageSize": 25,
      "sort": "DATE_PUBLI_DESC"
    }
  }

Returns a list of textCid / NOR / dates we map to DiscoveredPublication.
The document_url points to /consult/jorf/{textCid} which the extractor uses.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any, ClassVar

import httpx

from application.ports.customs_discovery import (
    DiscoveredPublication,
    ICustomsDiscoveryAdapter,
)
from infrastructure.config import get_settings
from infrastructure.customs.piste_oauth import PisteOAuthClient


class LegifranceDilaApiDiscovery:
    """Discovery adapter that calls PISTE/DILA JSON API directly."""

    name: ClassVar[str] = "legifrance-dila"
    # We POST to /search ourselves with OAuth; the use case's generic GET
    # pre-fetch would hit "405 Method Not Allowed". Skip it.
    requires_index_fetch: ClassVar[bool] = False

    def __init__(self) -> None:
        self._oauth: PisteOAuthClient | None = None

    def _client(self) -> PisteOAuthClient:
        if self._oauth is None:
            self._oauth = PisteOAuthClient(get_settings().piste)
        return self._oauth

    async def find_publications(
        self,
        *,
        index_html: str,  # ignored — kept for protocol compatibility
        index_url: str,
        config: dict[str, Any],
    ) -> Sequence[DiscoveredPublication]:
        settings = get_settings()
        # Title search restricted to homologation arrêtés. The DILA `JORF` fond
        # exposes `TITLE` (not the French `TITRE`) as the title field.
        query = config.get("query", "homologation prix tabacs manufactures")
        page_size = int(config.get("page_size", 25))
        max_pages = int(config.get("max_pages", 5))
        type_champ = config.get("type_champ", "TITLE")
        type_recherche = config.get("type_recherche", "TOUS_LES_MOTS_DANS_UN_CHAMP")
        # Post-filter on the result title (case-insensitive substrings, AND).
        # Belt-and-suspenders against any noise the title search lets through.
        title_must_contain: list[str] = [
            s.lower() for s in config.get("title_must_contain", ["homologation", "tabac"])
        ]
        # Optional nature filter (e.g. "ARRETE") — empty means no filter.
        nature_filter = (config.get("nature") or "").upper()

        headers = await self._client().auth_headers()
        out: list[DiscoveredPublication] = []
        seen: set[str] = set()

        async with httpx.AsyncClient(
            base_url=settings.piste.api_base_url, timeout=30, headers=headers
        ) as client:
            for page in range(1, max_pages + 1):
                response = await client.post(
                    "/search",
                    json={
                        "fond": "JORF",
                        "recherche": {
                            "champs": [
                                {
                                    "typeChamp": type_champ,
                                    "criteres": [
                                        {
                                            "typeRecherche": type_recherche,
                                            "valeur": query,
                                            "operateur": "ET",
                                        }
                                    ],
                                    "operateur": "ET",
                                }
                            ],
                            "filtres": [],
                            "operateur": "ET",
                            "pageNumber": page,
                            "pageSize": page_size,
                            "sort": "DATE_PUBLI_DESC",
                            "typePagination": "DEFAUT",
                        },
                    },
                )
                if response.status_code == 401:
                    self._client().invalidate()
                    response = await client.post(
                        "/search",
                        json={"fond": "JORF"},
                        headers=await self._client().auth_headers(),
                    )
                response.raise_for_status()
                payload = response.json()
                results = payload.get("results") or []
                if not results:
                    break

                for item in results:
                    if nature_filter and (item.get("nature") or "").upper() != nature_filter:
                        continue
                    pub = _to_discovery(
                        item,
                        settings.piste.api_base_url,
                        title_must_contain=title_must_contain,
                    )
                    if pub is None or pub.regulator_reference in seen:
                        continue
                    seen.add(pub.regulator_reference)
                    out.append(pub)

                if len(results) < page_size:
                    break

        return out


def _to_discovery(
    item: dict[str, Any],
    api_base: str,
    *,
    title_must_contain: list[str] | None = None,
) -> DiscoveredPublication | None:
    """Map one DILA search result into a DiscoveredPublication.

    Real shape (abridged, observed on the live PISTE API):
        {
          "titles": [
            {
              "id": "JORFTEXT000045570980_01-01-2999",
              "cid": "JORFTEXT000045570980",
              "title": "Décret n° 2022-545 du 13 avril 2022 portant…",
              "startDate": null, "endDate": null
            }
          ],
          "nor": "JUSC2204863D",
          "datePublication": "2022-04-14T00:00:00.000+0000",
          "nature": "DECRET",
          "jorfText": "JORF n°0088 du 14 avril 2022",
          ...
        }
    """

    titles = item.get("titles") or []
    if not titles:
        return None
    head = titles[0]

    # NOR lives at top level on this fond, fall back to title-level just in case.
    nor = item.get("nor") or head.get("nor") or head.get("cid") or head.get("id")
    if not nor:
        return None

    title_text = (head.get("title") or "").lower()
    if title_must_contain:
        if not all(token in title_text for token in title_must_contain):
            return None

    text_id = head.get("cid") or head.get("id") or nor
    document_url = f"{api_base.rstrip('/')}/consult/jorf/{text_id}"

    pub_date = _parse_iso_date(
        item.get("datePublication") or item.get("datePubli") or head.get("datePubli")
    )
    eff_date = _parse_iso_date(
        head.get("startDate") or head.get("dateDebut") or item.get("startDate")
    )

    return DiscoveredPublication(
        regulator_reference=nor,
        document_url=document_url,
        publication_date=pub_date,
        effective_date=eff_date,
        document_mime="application/json",
    )


def _parse_iso_date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
