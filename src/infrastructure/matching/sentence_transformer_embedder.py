# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""sentence-transformers embedder — runs in the worker process.

The chosen model (``paraphrase-multilingual-mpnet-base-v2``) was selected as
the precision sweet spot for French/English commercial labels: 768-d, ~420 MB
on disk, strong on paraphrase tasks across romance and germanic languages.

The model is *lazy-loaded* on first call and cached on the instance. Calling
``encode`` from an async context delegates to a thread to keep the event loop
free; sentence-transformers itself is purely synchronous.

Output vectors are L2-normalized (``normalize_embeddings=True``) so cosine
similarity reduces to a dot product, matching the HNSW ``vector_cosine_ops``
indexes declared on the embedding columns.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from threading import Lock
from typing import ClassVar

from infrastructure.observability.logging import get_logger


_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
_MODEL_DIM = 768


class SentenceTransformerEmbedder:
    name: ClassVar[str] = "st-mpnet-multilingual"
    dim: ClassVar[int] = _MODEL_DIM

    def __init__(
        self,
        *,
        model_name: str = _MODEL_NAME,
        batch_size: int = 64,
        device: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._batch_size = batch_size
        self._device = device  # None → auto (CPU when torch can't see CUDA)
        self._model = None
        self._lock = Lock()
        self._log = get_logger("embedder.sentence_transformer")

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            self._log.info("loading_embedder_model", model=self._model_name)
            # Imported lazily so import-time cost (and torch warm-up) is paid
            # in the worker process, not when the CLI does `from … import *`.
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name, device=self._device)
            self._log.info(
                "embedder_model_ready", dim=self._model.get_sentence_embedding_dimension()
            )

    def _encode_sync(self, texts: Sequence[str]) -> list[list[float]]:
        self._ensure_loaded()
        assert self._model is not None
        # convert_to_numpy=True is fine; we cast at the boundary.
        vectors = self._model.encode(
            list(texts),
            batch_size=self._batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [vec.tolist() for vec in vectors]

    async def encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        # CPU-bound work: hand off to a thread to keep the event loop alive
        # for other coroutines (DB I/O, Redis, …).
        return await asyncio.to_thread(self._encode_sync, texts)
