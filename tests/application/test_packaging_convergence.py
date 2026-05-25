# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.fetcher import FetchRequest, FetchResponse
from application.services.extraction_mapping import (
    cigar_slug_from,
    strip_pack_suffix,
)
from application.use_cases.ingest_product import (
    IngestOutcome,
    IngestProductUrlUseCase,
)
from infrastructure.parsers.mistercigar import MistercigarProductParser
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parents[1] / "fixtures"
SOURCE_URL_X1 = "https://mistercigar.com/boutique/cigares/cigares-a-lunite/vallejuelo-churchill-1/"


# ---- pure unit ------------------------------------------------------------


def test_strip_pack_suffix() -> None:
    assert strip_pack_suffix("Vallejuelo Churchill (1)") == "Vallejuelo Churchill"
    assert strip_pack_suffix("Vallejuelo Churchill (25)") == "Vallejuelo Churchill"
    assert strip_pack_suffix("Vallejuelo Churchill") == "Vallejuelo Churchill"
    # No double-strip of inner parentheses
    assert strip_pack_suffix("Cohiba Behike (special) (5)") == "Cohiba Behike (special)"


def test_cigar_slug_converges_across_packagings() -> None:
    s1 = cigar_slug_from("Vallejuelo", "Vallejuelo Churchill (1)")
    s5 = cigar_slug_from("Vallejuelo", "Vallejuelo Churchill (5)")
    s25 = cigar_slug_from("Vallejuelo", "Vallejuelo Churchill (25)")
    assert s1 == s5 == s25 == "vallejuelo-vallejuelo-churchill"


# ---- e2e convergence -----------------------------------------------------


def _make_packaged_html(base_html: str, pack_size: int) -> bytes:
    """Synthesise a fiche HTML for a different pack size from the captured x1.

    Replace the title "(1)" with "(N)" and the Packing attribute value 1 with N,
    plus the JSON-LD sku to keep things distinct.
    """

    body = base_html
    body = body.replace("Vallejuelo Churchill (1)", f"Vallejuelo Churchill ({pack_size})")
    # The Packing attribute row : <td ...><p>1</p></td> in WC attributes.
    body = re.sub(
        r"(attribute_pa_packing.+?<td[^>]*><p>)\s*1\s*(</p>)",
        rf"\g<1>{pack_size}\g<2>",
        body,
        count=1,
        flags=re.DOTALL,
    )
    # Unique SKU per packaging so we can verify per-pack identity
    body = body.replace("CIGDO01VANO001C", f"CIGDO0{pack_size}VANO001C")
    return body.encode("utf-8")


@pytest.fixture(scope="session")
def detail_body_x1() -> bytes:
    return (FIXTURES / "mistercigar_detail.html").read_bytes()


class _CannedFetcher:
    def __init__(self, *, body: bytes) -> None:
        self._body = body

    async def fetch(self, request: FetchRequest) -> FetchResponse:
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            body=self._body,
            elapsed_s=0.01,
            fetched_at=datetime.now(tz=UTC),
        )

    async def aclose(self) -> None:
        return None


async def _ingest(
    session_factory: async_sessionmaker[AsyncSession],
    body: bytes,
    url: str,
) -> IngestOutcome:
    use_case = IngestProductUrlUseCase(
        fetcher=_CannedFetcher(body=body),
        parser=MistercigarProductParser(),
    )
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        result = await use_case.execute(url=url, uow=uow)
    return result.outcome


async def test_three_packagings_produce_one_cigar(
    session_factory: async_sessionmaker[AsyncSession],
    clean_db: None,
    detail_body_x1: bytes,
) -> None:
    base = detail_body_x1.decode("utf-8")
    cases = [
        (detail_body_x1, SOURCE_URL_X1, 1),
        (
            _make_packaged_html(base, 5),
            SOURCE_URL_X1.replace("vallejuelo-churchill-1", "vallejuelo-churchill-5"),
            5,
        ),
        (
            _make_packaged_html(base, 25),
            SOURCE_URL_X1.replace("vallejuelo-churchill-1", "vallejuelo-churchill-25"),
            25,
        ),
    ]
    for body, url, _ in cases:
        await _ingest(session_factory, body, url)

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        cigars_count = await uow.cigars.count()
        cigar = await uow.cigars.get_by_slug("vallejuelo-vallejuelo-churchill")
        assert cigar is not None
        packages = await uow.cigar_packages.find_for_cigar(cigar.id)
        records = await uow.source_records.find_for_cigar(cigar.id)

    assert cigars_count == 1, "all three packagings must converge to one cigar"
    assert cigar.full_name == "Vallejuelo Churchill"  # stripped, no "(1)"
    assert {pkg.pack_size for pkg in packages} == {1, 5, 25}
    assert len(records) == 3  # one audit per fetch


async def test_re_ingest_same_packaging_refreshes_price(
    session_factory: async_sessionmaker[AsyncSession],
    clean_db: None,
    detail_body_x1: bytes,
) -> None:
    # First ingestion (price in fixture is 13.00 CHF)
    await _ingest(session_factory, detail_body_x1, SOURCE_URL_X1)

    # Tweak the JSON-LD price in the body (no space after colon in the wild) and re-ingest
    tampered = detail_body_x1.replace(b'"price":"13.00"', b'"price":"14.50"')
    await _ingest(session_factory, tampered, SOURCE_URL_X1)

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        cigar = await uow.cigars.get_by_slug("vallejuelo-vallejuelo-churchill")
        assert cigar is not None
        packages = await uow.cigar_packages.find_for_cigar(cigar.id)

    assert len(packages) == 1
    assert packages[0].pack_size == 1
    assert packages[0].price_amount == Decimal("14.50")
    assert packages[0].price_currency == "CHF"
