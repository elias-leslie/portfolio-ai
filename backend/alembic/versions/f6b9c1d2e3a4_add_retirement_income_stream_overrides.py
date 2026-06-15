"""add retirement income stream overrides

Revision ID: f6b9c1d2e3a4
Revises: e7d2a9c4b6f1
Create Date: 2026-06-15 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6b9c1d2e3a4"
down_revision: str | Sequence[str] | None = "e7d2a9c4b6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "retirement_income_stream_overrides",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("stream_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("owner_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("merged_into_stream_key", sa.String(length=64), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IS NULL OR status IN "
            "('active', 'stopped', 'one_off', 'portfolio_yield', 'ignored', 'merged')",
            name="ck_retirement_income_stream_overrides_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_retirement_income_stream_overrides_stream_key",
        "retirement_income_stream_overrides",
        ["stream_key"],
        unique=True,
    )
    op.create_index(
        "ix_retirement_income_stream_overrides_updated",
        "retirement_income_stream_overrides",
        [sa.text("updated_at DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_retirement_income_stream_overrides_updated",
        table_name="retirement_income_stream_overrides",
    )
    op.drop_index(
        "uq_retirement_income_stream_overrides_stream_key",
        table_name="retirement_income_stream_overrides",
    )
    op.drop_table("retirement_income_stream_overrides")
