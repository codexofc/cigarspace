"""matching pipeline: pgvector + status workflow + signals

Revision ID: c8328fd19696
Revises: 6b78342bf049
Create Date: 2026-05-25 05:00:00.000000+00:00

Adds the cigar/customs matching pipeline:
- enables the pgvector extension,
- adds embedding vector(768) on cigar and customs_price_entry (+ HNSW),
- extends match_method with 'hybrid',
- creates the customs_match_status enum,
- adds status / pack_size_bucket / signals to cigar_customs_match,
- creates a partial index on the PENDING_REVIEW review queue.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "c8328fd19696"
down_revision: str | Sequence[str] | None = "6b78342bf049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_EMBEDDING_DIM = 768


def upgrade() -> None:
    # ------------------------------------------------------------------
    # pgvector
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ------------------------------------------------------------------
    # New enum + extension of existing one
    # ------------------------------------------------------------------
    op.execute(
        "CREATE TYPE customs_match_status AS ENUM ("
        "'AUTO_ACCEPTED','PENDING_REVIEW','AUTO_REJECTED',"
        "'HUMAN_ACCEPTED','HUMAN_REJECTED')"
    )
    # ALTER TYPE ADD VALUE can run inside a transaction in PG12+ as long as
    # the new label is not consumed in the same transaction (it isn't here).
    # Match SQLAlchemy SAEnum(native_enum=True) which stores the Python *names*
    # (uppercase), not the enum values — keeping consistency with the original
    # match_method labels (EXACT/FUZZY/EMBEDDING/MANUAL).
    op.execute("ALTER TYPE match_method ADD VALUE IF NOT EXISTS 'HYBRID'")

    # ------------------------------------------------------------------
    # Embedding columns + HNSW indexes
    # ------------------------------------------------------------------
    op.add_column(
        "cigar",
        sa.Column("embedding", Vector(_EMBEDDING_DIM), nullable=True),
    )
    op.add_column(
        "customs_price_entry",
        sa.Column("embedding", Vector(_EMBEDDING_DIM), nullable=True),
    )
    op.execute(
        "CREATE INDEX ix_cigar_embedding_hnsw "
        "ON cigar USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX ix_customs_price_entry_embedding_hnsw "
        "ON customs_price_entry USING hnsw (embedding vector_cosine_ops)"
    )

    # ------------------------------------------------------------------
    # cigar_customs_match: status workflow + audit signals
    # ------------------------------------------------------------------
    op.add_column(
        "cigar_customs_match",
        sa.Column(
            "status",
            sa.Enum(
                "AUTO_ACCEPTED",
                "PENDING_REVIEW",
                "AUTO_REJECTED",
                "HUMAN_ACCEPTED",
                "HUMAN_REJECTED",
                name="customs_match_status",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING_REVIEW",
        ),
    )
    op.add_column(
        "cigar_customs_match",
        sa.Column("pack_size_bucket", sa.Integer(), nullable=True),
    )
    op.add_column(
        "cigar_customs_match",
        sa.Column(
            "signals",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(
        "ix_cigar_customs_match_status",
        "cigar_customs_match",
        ["status"],
        unique=False,
    )
    # Partial index dedicated to the human triage queue — kept cheap because
    # PENDING_REVIEW is a tiny minority of rows in steady state.
    op.execute(
        "CREATE INDEX ix_cigar_customs_match_pending_review "
        "ON cigar_customs_match (matched_at) "
        "WHERE status = 'PENDING_REVIEW'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cigar_customs_match_pending_review")
    op.drop_index("ix_cigar_customs_match_status", table_name="cigar_customs_match")
    op.drop_column("cigar_customs_match", "signals")
    op.drop_column("cigar_customs_match", "pack_size_bucket")
    op.drop_column("cigar_customs_match", "status")

    op.execute("DROP INDEX IF EXISTS ix_customs_price_entry_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_cigar_embedding_hnsw")
    op.drop_column("customs_price_entry", "embedding")
    op.drop_column("cigar", "embedding")

    op.execute("DROP TYPE IF EXISTS customs_match_status")
    # PG has no easy way to drop an enum value; we leave 'hybrid' in
    # match_method (harmless when unused).

    op.execute("DROP EXTENSION IF EXISTS vector")
