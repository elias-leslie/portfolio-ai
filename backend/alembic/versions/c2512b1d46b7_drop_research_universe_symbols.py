"""drop research_universe_symbols

Revision ID: c2512b1d46b7
Revises: e7f8a9b0c1d2
Create Date: 2026-05-10 21:22:11.777872

Drops the research_universe_symbols table and its supporting index after the
weekly S&P 500 universe refresh workflow (research_universe_refresh_wf) and
ingestion task (research_universe.py) were removed. No remaining code consumes
this table.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2512b1d46b7"
down_revision: str | Sequence[str] | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_research_universe_symbols_active")
    op.execute("DROP TABLE IF EXISTS research_universe_symbols CASCADE")


def downgrade() -> None:
    op.create_table(
        "research_universe_symbols",
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("symbol"),
    )
    op.create_index(
        "ix_research_universe_symbols_active",
        "research_universe_symbols",
        ["symbol"],
        postgresql_where=sa.text("removed_at IS NULL"),
    )
