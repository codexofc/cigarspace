# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from datetime import date
from pathlib import Path

from infrastructure.customs.discovery.legifrance_jorf import LegifranceJorfDiscovery

FIXTURE = Path(__file__).parents[2] / "fixtures" / "customs" / "legifrance_index_synthetic.html"
INDEX_URL = (
    "https://www.legifrance.gouv.fr/search/jorf"
    "?fonds=JORF&query=homologation+prix+tabac&searchField=ALL&tab_selection=jorf"
)


async def test_finds_expected_publications() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    result = await LegifranceJorfDiscovery().find_publications(
        index_html=html, index_url=INDEX_URL, config={}
    )

    refs = {p.regulator_reference for p in result}
    assert refs == {"ECOI1932471A", "ECOI1928912A", "ECOI1923456A"}


async def test_extracts_dates_and_canonical_urls() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    result = await LegifranceJorfDiscovery().find_publications(
        index_html=html, index_url=INDEX_URL, config={}
    )
    by_ref = {p.regulator_reference: p for p in result}

    a = by_ref["ECOI1932471A"]
    assert a.document_url == "https://www.legifrance.gouv.fr/jorf/id/ECOI1932471A"
    assert a.publication_date == date(2019, 12, 4)
    assert a.effective_date == date(2020, 1, 1)
    assert a.document_mime == "text/html"

    b = by_ref["ECOI1928912A"]
    assert b.publication_date == date(2019, 10, 11)
    assert b.effective_date == date(2019, 11, 4)


async def test_deduplicates_nor_seen_twice() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    result = await LegifranceJorfDiscovery().find_publications(
        index_html=html, index_url=INDEX_URL, config={}
    )
    refs = [p.regulator_reference for p in result]
    assert len(refs) == len(set(refs))


async def test_returns_empty_on_unrelated_html() -> None:
    result = await LegifranceJorfDiscovery().find_publications(
        index_html="<html><body>no NOR here at all</body></html>",
        index_url=INDEX_URL,
        config={},
    )
    assert list(result) == []
