# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.entities.brand import Brand
from domain.entities.cigar import BlendComponent, Cigar
from domain.entities.cigar_line import CigarLine
from domain.enums import (
    BlendComponentType,
    Confidence,
    FormatCategory,
    Intensity,
)
from domain.value_objects.flavor_profile import FlavorProfile
from infrastructure.persistence.repositories.brand import PgBrandRepository
from infrastructure.persistence.repositories.cigar import (
    PgCigarLineRepository,
    PgCigarRepository,
)

pytestmark = pytest.mark.integration


async def _seed_line(session_factory: async_sessionmaker[AsyncSession]) -> CigarLine:
    async with session_factory() as s:
        brand = await PgBrandRepository(s).add(Brand(slug="cohiba", name="Cohiba"))
        line = await PgCigarLineRepository(s).add(
            CigarLine(brand_id=brand.id, slug="behike", name="Behike")
        )
        await s.commit()
    return line


async def test_add_cigar_with_blend(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    line = await _seed_line(session_factory)

    cigar = Cigar(
        line_id=line.id,
        slug="cohiba-behike-bhk-52",
        full_name="Cohiba Behike BHK 52",
        vitola_name="BHK 52",
        format_category=FormatCategory.ROBUSTO,
        length_mm=Decimal("119"),
        ring_gauge=52,
        strength=Intensity.MEDIUM_FULL,
        body=Intensity.MEDIUM_FULL,
        flavor_profile=FlavorProfile(earthy=8.0, leather=7.5, coffee=6.0),
        is_cuban=True,
        is_handmade=True,
        blend_components=[
            BlendComponent(
                component_type=BlendComponentType.WRAPPER,
                tobacco_origin="CUB",
                source_confidence=Confidence.HIGH,
            ),
            BlendComponent(
                component_type=BlendComponentType.FILLER_LIGERO,
                tobacco_origin="CUB",
                tobacco_region="Vuelta Abajo",
                source_confidence=Confidence.HIGH,
            ),
        ],
    )

    async with session_factory() as s:
        repo = PgCigarRepository(s)
        created = await repo.add(cigar)
        await s.commit()

    async with session_factory() as s:
        repo = PgCigarRepository(s)
        found = await repo.get_by_slug("cohiba-behike-bhk-52")

    assert found is not None
    assert found.id == created.id
    assert found.is_cuban is True
    assert found.flavor_profile.earthy == 8.0
    assert len(found.blend_components) == 2
    components_by_type = {bc.component_type for bc in found.blend_components}
    assert BlendComponentType.WRAPPER in components_by_type
    assert BlendComponentType.FILLER_LIGERO in components_by_type


async def test_update_cigar_replaces_blend(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    line = await _seed_line(session_factory)
    cigar = Cigar(
        line_id=line.id,
        slug="cohiba-robusto",
        full_name="Cohiba Robusto",
        vitola_name="Robusto",
        blend_components=[
            BlendComponent(component_type=BlendComponentType.WRAPPER, tobacco_origin="CUB"),
        ],
    )

    async with session_factory() as s:
        created = await PgCigarRepository(s).add(cigar)
        await s.commit()

    updated = created.model_copy(
        update={
            "blend_components": [
                BlendComponent(
                    component_type=BlendComponentType.WRAPPER,
                    tobacco_origin="CUB",
                    source_confidence=Confidence.HIGH,
                ),
                BlendComponent(
                    component_type=BlendComponentType.BINDER,
                    tobacco_origin="CUB",
                ),
            ]
        }
    )

    async with session_factory() as s:
        result = await PgCigarRepository(s).update(updated)
        await s.commit()

    assert len(result.blend_components) == 2
    assert {bc.component_type for bc in result.blend_components} == {
        BlendComponentType.WRAPPER,
        BlendComponentType.BINDER,
    }


async def test_list_by_line(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    line = await _seed_line(session_factory)

    async with session_factory() as s:
        repo = PgCigarRepository(s)
        await repo.add(
            Cigar(
                line_id=line.id,
                slug="cohiba-behike-bhk-52",
                full_name="BHK 52",
                vitola_name="BHK 52",
            )
        )
        await repo.add(
            Cigar(
                line_id=line.id,
                slug="cohiba-behike-bhk-54",
                full_name="BHK 54",
                vitola_name="BHK 54",
            )
        )
        await s.commit()

    async with session_factory() as s:
        items = await PgCigarRepository(s).list_by_line(line.id)
        total = await PgCigarRepository(s).count()

    assert len(items) == 2
    assert total == 2
