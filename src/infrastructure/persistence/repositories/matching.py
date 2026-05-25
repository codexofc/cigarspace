# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""PostgreSQL implementation of the matching repository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from application.ports.matching_repository import (
    CigarMatchingContext,
    CustomsCandidate,
    EmbeddingJob,
)
from infrastructure.persistence.models import (
    CigarModel,
    CustomsPriceEntryModel,
)


# Canonical SQL that builds the embedding text for a cigar. Kept here (not in
# the Python normalization layer) because it lets us push the work into the
# DB and avoids materializing every row in Python when we only need the text.
# ``regexp_replace(..., '\([^)]*\)', '', 'g')`` strips merchant-side pack
# annotations like ``(10 X 5)`` that pollute the embedding without carrying
# product semantics. We keep brand + line + full_name; the vitola is almost
# always already inside the full_name on every parser we ship.
_CIGAR_TEXT_SQL = text(
    """
    SELECT cigar.id AS id,
           TRIM(regexp_replace(
                  CONCAT_WS(' ',
                            brand.name,
                            cigar_line.name,
                            cigar.full_name),
                  '\\([^)]*\\)', '', 'g')) AS text
      FROM cigar
      JOIN cigar_line ON cigar_line.id = cigar.line_id
      JOIN brand ON brand.id = cigar_line.brand_id
     WHERE cigar.embedding IS NULL
     ORDER BY cigar.created_at NULLS LAST
     LIMIT :limit
    """
)


_CUSTOMS_TEXT_SQL = text(
    """
    SELECT id,
           TRIM(CONCAT_WS(' ',
                          NULLIF(raw_brand_label, ''),
                          raw_product_label)) AS text
      FROM customs_price_entry
     WHERE embedding IS NULL
       AND tax_class ILIKE :tax_class_like
     ORDER BY created_at NULLS LAST
     LIMIT :limit
    """
)


# Vector recall query. ORDER BY by the `<=>` cosine distance operator uses
# the HNSW index we created on the column. We also surface the distance
# directly so the caller can derive a per-candidate score without re-querying.
_VECTOR_RECALL_SQL = text(
    """
    SELECT id,
           raw_brand_label,
           raw_product_label,
           packaging_description,
           pack_size,
           unit_price,
           (embedding <=> CAST(:cigar_embedding AS vector)) AS cosine_distance
      FROM customs_price_entry
     WHERE country_code = :country_code
       AND embedding IS NOT NULL
       AND tax_class ILIKE :tax_class_like
     ORDER BY embedding <=> CAST(:cigar_embedding AS vector)
     LIMIT :k
    """
)


def _vector_literal(vec: Sequence[float]) -> str:
    """pgvector accepts the textual ``[1,2,3]`` form for binds."""
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


def _coerce_vector(value: object) -> list[float] | None:
    """pgvector columns may come back as ``list[float]`` (typed column) or
    as the raw textual ``"[1,2,3]"`` form (raw ``text()`` queries). Normalise
    to ``list[float]`` regardless of the path used."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip().lstrip("[").rstrip("]")
        if not stripped:
            return []
        return [float(p) for p in stripped.split(",")]
    return [float(x) for x in value]


class PgMatchingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def iter_cigars_without_embedding(self, *, limit: int) -> Sequence[EmbeddingJob]:
        result = await self._session.execute(_CIGAR_TEXT_SQL, {"limit": limit})
        return [EmbeddingJob(entity_id=row.id, text=row.text or "") for row in result]

    async def iter_customs_without_embedding(
        self, *, limit: int, tax_class_like: str = "%cigar%"
    ) -> Sequence[EmbeddingJob]:
        result = await self._session.execute(
            _CUSTOMS_TEXT_SQL, {"limit": limit, "tax_class_like": tax_class_like}
        )
        return [EmbeddingJob(entity_id=row.id, text=row.text or "") for row in result]

    async def set_cigar_embeddings(self, embeddings: Sequence[tuple[UUID, list[float]]]) -> int:
        if not embeddings:
            return 0
        stmt = (
            CigarModel.__table__.update()
            .where(CigarModel.id == bindparam("_id"))
            .values(embedding=bindparam("_emb"))
        )
        await self._session.execute(
            stmt,
            [{"_id": eid, "_emb": vec} for eid, vec in embeddings],
        )
        return len(embeddings)

    async def set_customs_embeddings(self, embeddings: Sequence[tuple[UUID, list[float]]]) -> int:
        if not embeddings:
            return 0
        stmt = (
            CustomsPriceEntryModel.__table__.update()
            .where(CustomsPriceEntryModel.id == bindparam("_id"))
            .values(embedding=bindparam("_emb"))
        )
        await self._session.execute(
            stmt,
            [{"_id": eid, "_emb": vec} for eid, vec in embeddings],
        )
        return len(embeddings)

    async def get_cigar_embedding(self, cigar_id: UUID) -> list[float] | None:
        result = await self._session.execute(
            select(CigarModel.embedding).where(CigarModel.id == cigar_id)
        )
        return _coerce_vector(result.scalar_one_or_none())

    async def get_cigar_context(self, cigar_id: UUID) -> CigarMatchingContext | None:
        result = await self._session.execute(
            text(
                """
                SELECT TRIM(regexp_replace(
                              CONCAT_WS(' ',
                                        brand.name,
                                        cigar_line.name,
                                        cigar.full_name),
                              '\\([^)]*\\)', '', 'g')) AS text,
                       cigar.embedding AS embedding,
                       COALESCE(
                         (SELECT array_agg(DISTINCT pack_size ORDER BY pack_size)
                            FROM cigar_package
                           WHERE cigar_package.cigar_id = cigar.id),
                         ARRAY[]::integer[]
                       ) AS pack_sizes
                  FROM cigar
                  JOIN cigar_line ON cigar_line.id = cigar.line_id
                  JOIN brand ON brand.id = cigar_line.brand_id
                 WHERE cigar.id = :cigar_id
                """
            ),
            {"cigar_id": cigar_id},
        )
        row = result.first()
        if row is None:
            return None
        return CigarMatchingContext(
            text=row.text or "",
            embedding=_coerce_vector(row.embedding),
            pack_sizes=tuple(row.pack_sizes or ()),
        )

    async def list_cigar_ids_with_embedding(self, *, limit: int | None = None) -> Sequence[UUID]:
        stmt = select(CigarModel.id).where(CigarModel.embedding.is_not(None))
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]

    async def find_top_k_cigars_by_vector(
        self, *, query_embedding: list[float], k: int = 50
    ) -> Sequence[tuple[UUID, float]]:
        if not query_embedding:
            return []
        stmt = text(
            """
            SELECT id, (embedding <=> CAST(:vec AS vector)) AS distance
              FROM cigar
             WHERE embedding IS NOT NULL
             ORDER BY embedding <=> CAST(:vec AS vector)
             LIMIT :k
            """
        )
        result = await self._session.execute(
            stmt, {"vec": _vector_literal(query_embedding), "k": k}
        )
        return [(row.id, float(row.distance)) for row in result]

    async def fulltext_search_cigars(
        self, *, query: str, k: int = 50
    ) -> Sequence[tuple[UUID, float]]:
        if not query.strip():
            return []
        # Trigram similarity on cigar.full_name + brand.name; pg_trgm's `%`
        # operator uses the GIN indexes we created in  migration.
        stmt = text(
            """
            SELECT cigar.id AS id,
                   GREATEST(
                     similarity(lower(cigar.full_name), :q),
                     similarity(lower(brand.name) || ' ' || lower(cigar.full_name), :q),
                     CASE WHEN cigar.slug ILIKE :q_like THEN 0.5 ELSE 0 END
                   ) AS score
              FROM cigar
              JOIN cigar_line ON cigar_line.id = cigar.line_id
              JOIN brand ON brand.id = cigar_line.brand_id
             WHERE lower(cigar.full_name) % :q
                OR lower(brand.name) % :q
                OR cigar.slug ILIKE :q_like
             ORDER BY score DESC
             LIMIT :k
            """
        )
        result = await self._session.execute(
            stmt,
            {
                "q": query.lower(),
                "q_like": f"%{query.lower()}%",
                "k": k,
            },
        )
        return [(row.id, float(row.score)) for row in result]

    async def find_top_k_for_cigar(
        self,
        *,
        cigar_embedding: list[float],
        k: int = 50,
        country_code: str = "FR",
        tax_class_like: str = "%cigar%",
    ) -> Sequence[CustomsCandidate]:
        if not cigar_embedding:
            return []
        result = await self._session.execute(
            _VECTOR_RECALL_SQL,
            {
                "cigar_embedding": _vector_literal(cigar_embedding),
                "k": k,
                "country_code": country_code,
                "tax_class_like": tax_class_like,
            },
        )
        return [
            CustomsCandidate(
                id=row.id,
                raw_brand_label=row.raw_brand_label,
                raw_product_label=row.raw_product_label,
                packaging_description=row.packaging_description,
                pack_size=row.pack_size,
                unit_price=row.unit_price,
                cosine_distance=float(row.cosine_distance),
            )
            for row in result
        ]
