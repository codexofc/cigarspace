# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Matching repository port — bulk embedding I/O + vector recall.

Kept separate from the per-entity repositories because the operations are
infrastructure-specific (pgvector, bulk UPDATE, HNSW search) and shouldn't
leak into the cleaner CRUD-ish ports we expose elsewhere.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class EmbeddingJob:
    """One row that still needs an embedding."""

    entity_id: UUID
    text: str


@dataclass(frozen=True)
class CigarMatchingContext:
    """Everything the matcher needs about one cigar in a single round-trip."""

    text: str
    embedding: list[float] | None
    pack_sizes: tuple[int, ...]


@dataclass(frozen=True)
class CustomsCandidate:
    """A customs entry surfaced by the vector recall step."""

    id: UUID
    raw_brand_label: str
    raw_product_label: str
    packaging_description: str | None
    pack_size: int | None
    unit_price: Decimal
    cosine_distance: float


class IMatchingRepository(Protocol):
    async def iter_cigars_without_embedding(self, *, limit: int) -> Sequence[EmbeddingJob]: ...

    async def set_cigar_embeddings(self, embeddings: Sequence[tuple[UUID, list[float]]]) -> int:
        """Bulk-update cigar.embedding; returns the number of rows touched."""

    async def iter_customs_without_embedding(
        self, *, limit: int, tax_class_like: str = "%cigar%"
    ) -> Sequence[EmbeddingJob]: ...

    async def set_customs_embeddings(
        self, embeddings: Sequence[tuple[UUID, list[float]]]
    ) -> int: ...

    async def get_cigar_embedding(self, cigar_id: UUID) -> list[float] | None: ...
    async def get_cigar_context(self, cigar_id: UUID) -> CigarMatchingContext | None: ...
    async def list_cigar_ids_with_embedding(
        self, *, limit: int | None = None
    ) -> Sequence[UUID]: ...

    async def find_top_k_for_cigar(
        self,
        *,
        cigar_embedding: list[float],
        k: int = 50,
        country_code: str = "FR",
        tax_class_like: str = "%cigar%",
    ) -> Sequence[CustomsCandidate]: ...

    async def find_top_k_cigars_by_vector(
        self, *, query_embedding: list[float], k: int = 50
    ) -> Sequence[tuple[UUID, float]]:
        """Top-K cigars by cosine distance to the query embedding.

        Returns ``[(cigar_id, cosine_distance)]`` sorted ascending by
        distance. Used by the hybrid search endpoint.
        """

    async def fulltext_search_cigars(
        self, *, query: str, k: int = 50
    ) -> Sequence[tuple[UUID, float]]:
        """Top-K cigars by trigram similarity on full_name / slug / brand.

        Returns ``[(cigar_id, similarity)]`` sorted descending by score.
        """
