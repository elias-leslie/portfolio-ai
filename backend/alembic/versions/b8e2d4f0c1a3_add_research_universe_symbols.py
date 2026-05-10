"""add research_universe_symbols

Revision ID: b8e2d4f0c1a3
Revises: d9b6a3e2f4c1
Create Date: 2026-05-10 19:30:00.000000

Tracks the broad research universe (e.g. S&P 500 constituents) separately
from the narrow watchlist. Sourced authoritatively from the iShares IVV
holdings file, refreshed weekly. Departures keep their row with
``removed_at`` set so historical backtests remain interpretable; arrivals
trigger an OHLCV backfill so the screening pipeline has data to work with.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8e2d4f0c1a3"
down_revision: str | Sequence[str] | None = "d9b6a3e2f4c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
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


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_research_universe_symbols_active",
        table_name="research_universe_symbols",
    )
    op.drop_table("research_universe_symbols")
