# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from datetime import date

from infrastructure.customs.discovery.douane_opendata import (
    DouaneOpenDataDiscovery,
)


_INDEX_HTML = """
<html><body>
  <ul>
    <li><a href="/sites/default/files/2026-05/07/Maquette%20JORF%201er%20juin%202026.ods">Télécharger le document</a></li>
    <li><a href="/sites/default/files/2026-05/07/Maquette%20JORF%201er%20juin%202026.pdf">Télécharger le document</a></li>
    <li><a href="/sites/default/files/2026-02/13/Maquette%20JORF%201er%20mars%202026.ods">Télécharger le document</a></li>
    <li><a href="/sites/default/files/2026-02/04/Maquette%20JORF%201er%20f%C3%A9vrier%202026.ods">Télécharger le document</a></li>
    <!-- noise -->
    <li><a href="/something/else.pdf">Unrelated PDF</a></li>
    <li><a href="https://external.example/file.ods">External ODS without "Maquette JORF" name</a></li>
  </ul>
</body></html>
"""


async def test_finds_one_publication_per_arrete_in_preferred_extension() -> None:
    d = DouaneOpenDataDiscovery()
    pubs = list(
        await d.find_publications(
            index_html=_INDEX_HTML,
            index_url="https://www.douane.gouv.fr/la-douane/opendata/categories/tabacs-manufactures",
            config={"prefer_extension": "ods"},
        )
    )
    refs = sorted(p.regulator_reference for p in pubs)
    assert refs == [
        "FR-DOUANE-2026-02-01",
        "FR-DOUANE-2026-03-01",
        "FR-DOUANE-2026-06-01",
    ]


async def test_extracts_effective_and_publication_dates() -> None:
    d = DouaneOpenDataDiscovery()
    pubs = {
        p.regulator_reference: p
        for p in await d.find_publications(
            index_html=_INDEX_HTML, index_url="https://example/", config={}
        )
    }
    june = pubs["FR-DOUANE-2026-06-01"]
    assert june.effective_date == date(2026, 6, 1)
    # /files/YYYY-MM/DD/... → publication on portal
    assert june.publication_date == date(2026, 5, 7)
    assert june.document_mime == "application/vnd.oasis.opendocument.spreadsheet"


async def test_resolves_relative_to_absolute_url() -> None:
    d = DouaneOpenDataDiscovery()
    pubs = await d.find_publications(
        index_html=_INDEX_HTML,
        index_url="https://www.douane.gouv.fr/la-douane/opendata/categories/tabacs-manufactures",
        config={},
    )
    for p in pubs:
        assert p.document_url.startswith("https://www.douane.gouv.fr/")


async def test_pdf_mode_returns_pdf_links() -> None:
    d = DouaneOpenDataDiscovery()
    pubs = list(
        await d.find_publications(
            index_html=_INDEX_HTML,
            index_url="https://example/",
            config={"prefer_extension": "pdf"},
        )
    )
    assert len(pubs) == 1
    assert pubs[0].document_url.endswith(".pdf")
    assert pubs[0].document_mime == "application/pdf"
