"""public API: pg_trgm + api_user + refresh_token + trigram indexes

Revision ID: be41166633b3
Revises: c8328fd19696
Create Date: 2026-05-25 07:00:00.000000+00:00

Bootstrap migration for the public HTTP API:
- enables `citext` (case-insensitive email column) and `pg_trgm` (fuzzy
  full-text search on cigar/brand/line names),
- creates the `api_user` and `refresh_token` tables,
- creates GIN trigram indexes that speed up the hybrid search endpoint.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "be41166633b3"
down_revision: str | Sequence[str] | None = "c8328fd19696"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ------------------------------------------------------------------
    # api_user
    # ------------------------------------------------------------------
    op.create_table(
        "api_user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.dialects.postgresql.CITEXT(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_user")),
        sa.UniqueConstraint("email", name="uq_api_user_email"),
    )

    # ------------------------------------------------------------------
    # refresh_token
    # ------------------------------------------------------------------
    op.create_table(
        "refresh_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.dialects.postgresql.INET(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["api_user.id"],
            name=op.f("fk_refresh_token_user_id_api_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_token")),
        sa.UniqueConstraint("token_hash", name="uq_refresh_token_hash"),
    )
    op.create_index(
        "ix_refresh_token_user_revoked",
        "refresh_token",
        ["user_id", "revoked_at"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # Trigram indexes on text fields used by /cigars/search full-text branch.
    # ------------------------------------------------------------------
    op.execute(
        "CREATE INDEX ix_cigar_full_name_trgm "
        "ON cigar USING gin (lower(full_name) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_cigar_slug_trgm "
        "ON cigar USING gin (slug gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_brand_name_trgm "
        "ON brand USING gin (lower(name) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_cigar_line_name_trgm "
        "ON cigar_line USING gin (lower(name) gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cigar_line_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_brand_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_cigar_slug_trgm")
    op.execute("DROP INDEX IF EXISTS ix_cigar_full_name_trgm")

    op.drop_index("ix_refresh_token_user_revoked", table_name="refresh_token")
    op.drop_table("refresh_token")
    op.drop_table("api_user")

    # We do not drop pg_trgm / citext extensions on downgrade — other parts
    # of the database may rely on them in the future and dropping is
    # destructive.
