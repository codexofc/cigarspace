# 3. pgvector for embedding storage and recall

Date: 2026-05-25

## Status

Accepted

## Context

The matching pipeline computes 768-dimensional dense embeddings for
both merchant cigars and customs price entries via `sentence-transformers`
(`paraphrase-multilingual-mpnet-base-v2`). At runtime we need to do
top-K cosine-distance lookups to surface the best matching candidates
for a given cigar.

Constraints:

- The catalogue stays in PostgreSQL (it is our single source of truth
  for relational data, FKs, transactions).
- We need ANN (approximate nearest neighbour) indexing — exact brute
  force at 10k+ rows × N cigars becomes the latency bottleneck.
- Operational simplicity: we want as few datastores as possible.

## Decision

We use the **pgvector** extension on PostgreSQL 16, with an **HNSW**
index using `vector_cosine_ops`.

- Embeddings live as `vector(768)` columns on the same rows they
  belong to (`cigar.embedding`, `customs_price_entry.embedding`).
- The Docker image is `pgvector/pgvector:pg16` so the extension is
  always present.
- The matching repository (`PgMatchingRepository.find_top_k_*`) issues
  `ORDER BY embedding <=> :query LIMIT :k` queries, which the HNSW
  index serves in sub-millisecond on our current data size.

Candidates considered:

| Option        | Why we did not pick it                                           |
| ------------- | ---------------------------------------------------------------- |
| **Standalone Qdrant / Weaviate / Milvus** | Adds a second datastore + sync logic; we lose transactional consistency between vector and relational columns. |
| **Faiss in-process** | Not persistent without bespoke serialization; rebuilds on every restart; awkward across worker + API processes. |
| **pgvector with IVFFlat** | Faster build, worse recall — HNSW wins for our scale. |

## Consequences

- Single backup process (PG-only) gives us ACID guarantees on
  embeddings AND relational data.
- Bumping the embedding dimensionality (e.g. switching to a 1024-d
  model) requires an Alembic migration that drops + recreates the
  column and the HNSW index — non-trivial but tracked.
- We accept pgvector's HNSW build cost (linear in N during initial
  build); not a problem at our scale (≤ 50k rows total today).
- pgvector's licensing is permissive (PostgreSQL License); no friction
  with our overall license.
