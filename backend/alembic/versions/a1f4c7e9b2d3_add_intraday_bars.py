"""add intraday_bars

Revision ID: a1f4c7e9b2d3
Revises: d3f8a1c6b9e2
Create Date: 2026-06-05 19:00:00.000000

Current-trading-day price path for the Investing > Symbols scanner. ``day_bars``
only carries completed daily sessions, so the scanner's "D" (Today) trendline had
no honest data to draw. This table holds intraday (5-minute) bars for watchlist
symbols, refreshed every few minutes during market hours by
``refresh_watchlist_intraday``. ``session_date`` is the US/Eastern trading date,
stored so the read path can pull "the latest session's bars" with one indexed
query instead of doing timezone math in the hot path.

Bars are pruned to a short rolling retention by the ingestion task, so this stays
small. Additive — nothing else depends on it yet.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1f4c7e9b2d3"
down_revision: str | Sequence[str] | None = "d3f8a1c6b9e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "intraday_bars",
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("ingest_run_id", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("symbol", "ts"),
    )
    # Latest-session read path: max(session_date) per symbol, then bars in time order.
    op.create_index(
        "idx_intraday_bars_symbol_session_ts",
        "intraday_bars",
        ["symbol", sa.text("session_date DESC"), "ts"],
    )


def downgrade() -> None:
    op.drop_index("idx_intraday_bars_symbol_session_ts", table_name="intraday_bars")
    op.drop_table("intraday_bars")
