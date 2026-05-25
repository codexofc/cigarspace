# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Shared fixtures for the FastAPI test suite.

The strategy:
- Build the FastAPI app once per session.
- Override the dependency that returns `session_factory` so every test
  goes through the throwaway `cigars_test` DB managed by the root
  conftest.
- Provide three HTTP clients: anonymous, reader (logged in), admin.

We avoid the embedder model by stubbing it with a deterministic fake.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import ClassVar

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from domain.entities.api_user import ApiUser
from domain.entities.brand import Brand
from domain.entities.cigar import Cigar
from domain.entities.cigar_line import CigarLine
from domain.entities.customs import (
    CustomsPriceEntry,
    CustomsPublication,
    CustomsSource,
)
from domain.enums import (
    CustomsPublicationStatus,
    FormatCategory,
)
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from presentation.api.dependencies import get_embedder, get_session_factory
from presentation.api.main import create_app
from presentation.api.security.password import hash_password

_DIM = 768


class FakeEmbedder:
    name: ClassVar[str] = "fake"
    dim: ClassVar[int] = _DIM

    async def encode(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            digest = hashlib.blake2b(text.encode("utf-8"), digest_size=32).digest()
            vec = [(digest[i % len(digest)] - 128) / 128.0 + (i % 7) * 0.01 for i in range(_DIM)]
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            out.append([x / norm for x in vec])
        return out


@pytest_asyncio.fixture
async def api_app(
    engine: AsyncEngine,
    session_factory: async_sessionmaker,
    clean_db: None,
):
    # slowapi keeps an in-memory counter at module level; reset it per
    # test so isolated cases don't trigger 429 against each other.
    from presentation.api.rate_limit import limiter as _limiter

    _limiter.reset()
    app = create_app()
    # Force the lifespan-driven globals via state for the test process.
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.embedder = FakeEmbedder()
    # Override dependency that pulls the session factory from app.state.
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_embedder] = lambda: app.state.embedder
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def api_client(api_app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def seeded_universe(session_factory):
    """Insert a tiny, deterministic dataset reachable by every API test."""

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        brand = await uow.brands.add(
            Brand(slug="cohiba", name="Cohiba", country_origin="CUB", is_active=True)
        )
        line = await uow.cigar_lines.add(CigarLine(brand_id=brand.id, slug="behike", name="Behike"))
        cigar = await uow.cigars.add(
            Cigar(
                line_id=line.id,
                slug="cohiba-behike-bhk-52",
                full_name="Cohiba Behike BHK 52",
                vitola_name="Robusto",
                format_category=FormatCategory.ROBUSTO,
                is_cuban=True,
            )
        )

        # Admin + reader users — referenced later by email; suppress F841.
        await uow.api_users.add(
            ApiUser(
                email="admin@example.com",
                full_name="Admin",
                password_hash=hash_password("admin-pass"),
                is_admin=True,
            )
        )
        await uow.api_users.add(
            ApiUser(
                email="reader@example.com",
                full_name="Reader",
                password_hash=hash_password("reader-pass"),
                is_admin=False,
            )
        )

        # Customs source + publication + 1 entry
        source = await uow.customs_sources.upsert(
            CustomsSource(
                code="fr-test",
                country_code="FR",
                display_name="FR Test",
                index_url="https://example/",
                discovery_parser_name="x",
                extraction_parser_name="y",
                default_currency_code="EUR",
                is_active=False,
            )
        )
        publication = await uow.customs_publications.add(
            CustomsPublication(
                source_id=source.id,
                regulator_reference="FR-TEST-1",
                document_url="https://example/doc",
                status=CustomsPublicationStatus.INGESTED,
                publication_date=date(2026, 6, 1),
                effective_date=date(2026, 6, 1),
            )
        )
        now = datetime.now(tz=UTC)
        entry = await uow.customs_prices.upsert(
            CustomsPriceEntry(
                publication_id=publication.id,
                country_code="FR",
                currency_code="EUR",
                unit_price=Decimal("12.00"),
                effective_date=date(2026, 6, 1),
                raw_brand_label="HABANOS",
                raw_product_label="Cohiba Behike BHK 52",
                packaging_description="en 10 cigares",
                pack_size=10,
                tax_class="Cigares et cigarillos",
                extracted_at=now,
                extractor_version="test-1.0",
            )
        )
        entry_single = await uow.customs_prices.upsert(
            CustomsPriceEntry(
                publication_id=publication.id,
                country_code="FR",
                currency_code="EUR",
                unit_price=Decimal("1.30"),
                effective_date=date(2026, 6, 1),
                raw_brand_label="HABANOS",
                raw_product_label="Cohiba Behike BHK 52",
                packaging_description="a l'unite",
                pack_size=1,
                tax_class="Cigares et cigarillos",
                extracted_at=now,
                extractor_version="test-1.0",
            )
        )
        await uow.commit()

    return {
        "brand_slug": "cohiba",
        "line_slug": "behike",
        "cigar_slug": "cohiba-behike-bhk-52",
        "cigar_id": str(cigar.id),
        "admin_email": "admin@example.com",
        "admin_password": "admin-pass",
        "reader_email": "reader@example.com",
        "reader_password": "reader-pass",
        "source_code": "fr-test",
        "publication_id": str(publication.id),
        "entry_id": str(entry.id),
        "entry_id_single": str(entry_single.id),
    }


async def _login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post(
        "/api/v1/oauth/token",
        json={"grant_type": "password", "email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def admin_token(api_client: AsyncClient, seeded_universe) -> str:
    return await _login(
        api_client,
        seeded_universe["admin_email"],
        seeded_universe["admin_password"],
    )


@pytest_asyncio.fixture
async def reader_token(api_client: AsyncClient, seeded_universe) -> str:
    return await _login(
        api_client,
        seeded_universe["reader_email"],
        seeded_universe["reader_password"],
    )
