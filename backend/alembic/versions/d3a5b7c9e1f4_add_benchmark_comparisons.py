"""add benchmark_comparisons

Revision ID: d3a5b7c9e1f4
Revises: c4f0e1d2a3b9
Create Date: 2026-05-10 19:55:00.000000

Per-(symbol, benchmark, screen_run_date) cache of buy-and-hold comparison
metrics. Lazily populated on first catalog request, naturally invalidated
when the next screen run produces a new run_date. Independent of the
benchmark catalog itself: adding a new benchmark to BENCHMARKS does not
require a schema change, just a deploy.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3a5b7c9e1f4"
down_revision: str | Sequence[str] | None = "c4f0e1d2a3b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "benchmark_comparisons",
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("benchmark_key", sa.String(length=32), nullable=False),
        sa.Column("screen_run_date", sa.Date(), nullable=False),
        sa.Column("backtest_start_date", sa.Date(), nullable=False),
        sa.Column("backtest_end_date", sa.Date(), nullable=False),
        sa.Column("strategy_return_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("benchmark_return_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("excess_return_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("benchmark_max_drawdown_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("benchmark_volatility_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("beats_benchmark", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("symbol", "benchmark_key", "screen_run_date"),
    )
    op.create_index(
        "ix_benchmark_comparisons_screen",
        "benchmark_comparisons",
        ["screen_run_date", sa.text("excess_return_pct DESC NULLS LAST")],
    )
    op.create_index(
        "ix_benchmark_comparisons_benchmark",
        "benchmark_comparisons",
        ["benchmark_key", "screen_run_date"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_benchmark_comparisons_benchmark", table_name="benchmark_comparisons")
    op.drop_index("ix_benchmark_comparisons_screen", table_name="benchmark_comparisons")
    op.drop_table("benchmark_comparisons")
