# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Embedding port — turn text into a dense vector for similarity search."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, Protocol


class IEmbedder(Protocol):
    """Stateless port that encodes a batch of strings into vectors.

    Implementations are free to lazy-load and cache an underlying model.
    The encoder must be normalized (unit-length output) so cosine and dot
    similarity coincide; this matches the HNSW indexes we declare on
    embedding columns (``vector_cosine_ops``).
    """

    name: ClassVar[str]
    dim: ClassVar[int]

    async def encode(self, texts: Sequence[str]) -> list[list[float]]:
        """Encode ``texts`` and return one vector per input, in order."""
        ...
