"""restore research_universe_symbols with sector + industry + weight

Revision ID: f8c9d1e4a2b7
Revises: e4a9c2d7f1b6
Create Date: 2026-05-17 17:00:00.000000

Restores the ``research_universe_symbols`` table that was dropped in
``c2512b1d46b7`` after the original weekly refresh workflow was removed.

This revival is a clone-forward of the original schema enriched with
``sector``, ``industry``, and ``weight`` columns to support the L1 macro
deployment gate (SPX breadth via member 200d MA), the L2 quantitative
scanner (S&P 500 universe), and downstream backtest harnesses.

Historical departures keep their row with ``removed_at`` set so walk-forward
replays can interpret point-in-time membership; arrivals trigger an OHLCV
backfill via the research-universe workflow.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8c9d1e4a2b7"
down_revision: str | Sequence[str] | None = "e4a9c2d7f1b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_universe_symbols",
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("sector", sa.String(length=64), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("weight", sa.Numeric(10, 6), nullable=True),
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
    op.create_index(
        "ix_research_universe_symbols_sector",
        "research_universe_symbols",
        ["sector"],
        postgresql_where=sa.text("removed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_universe_symbols_sector",
        table_name="research_universe_symbols",
    )
    op.drop_index(
        "ix_research_universe_symbols_active",
        table_name="research_universe_symbols",
    )
    op.drop_table("research_universe_symbols")
