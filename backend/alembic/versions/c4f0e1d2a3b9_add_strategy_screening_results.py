"""add strategy_screening_results

Revision ID: c4f0e1d2a3b9
Revises: b8e2d4f0c1a3
Create Date: 2026-05-10 19:50:00.000000

Persists per-symbol walk-forward screening output for the research
universe. Each row is one (symbol, strategy_type, run_date) backtest
sweep. The catalog UI reads from this table to surface ranked candidates;
the weekly screening task UPSERTs over the prior week's run.

edge_score is a denormalized composite (Sharpe x significance x
beat-buy-and-hold consistency) so the index can sort the catalog
cheaply without recomputing on every read.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4f0e1d2a3b9"
down_revision: str | Sequence[str] | None = "b8e2d4f0c1a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "strategy_screening_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("strategy_type", sa.String(length=32), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("backtest_start_date", sa.Date(), nullable=True),
        sa.Column("backtest_end_date", sa.Date(), nullable=True),
        sa.Column("num_folds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mean_sharpe", sa.Numeric(10, 4), nullable=True),
        sa.Column("std_sharpe", sa.Numeric(10, 4), nullable=True),
        sa.Column("mean_win_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("max_drawdown_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("mean_excess_vs_bh", sa.Numeric(10, 4), nullable=True),
        sa.Column("pct_folds_beat_bh", sa.Numeric(5, 4), nullable=True),
        sa.Column("wilcoxon_p_value", sa.Numeric(10, 6), nullable=True),
        sa.Column("statistically_significant", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("significance_level", sa.String(length=16), nullable=True),
        sa.Column("edge_score", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "folds_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol", "strategy_type", "run_date",
            name="uq_screening_symbol_strategy_run",
        ),
    )
    op.create_index(
        "ix_screening_edge",
        "strategy_screening_results",
        [sa.text("edge_score DESC NULLS LAST"), sa.text("run_date DESC")],
    )
    op.create_index(
        "ix_screening_run_date",
        "strategy_screening_results",
        [sa.text("run_date DESC")],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_screening_run_date", table_name="strategy_screening_results")
    op.drop_index("ix_screening_edge", table_name="strategy_screening_results")
    op.drop_table("strategy_screening_results")
