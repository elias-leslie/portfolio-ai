"""add signal_scanner_runs + signal_scanner_scores

Revision ID: fa0e3b7c5d29
Revises: f9d2e5a8b3c1
Create Date: 2026-05-17 21:00:00.000000

Phase 2 — L2 quantitative scanner. ``signal_scanner_runs`` is a header
row per scanner pass (one per macro_gate event in practice); each pass
has zero-to-N ``signal_scanner_scores`` rows depending on macro gate
behaviour (FULL = all members, REDUCED = composite_pct > 75 only,
DEFENSIVE = empty run with ``skip_reason='gate_defensive'``).

Five factor values + five universe-relative percentiles + composite
percentile + final rank are persisted per symbol so the API and the L3
fan-out can re-rank or threshold without recomputing factors.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "fa0e3b7c5d29"
down_revision: str | Sequence[str] | None = "f9d2e5a8b3c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signal_scanner_runs",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("gate_zone", sa.String(length=16), nullable=False),
        sa.Column("gate_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("universe_size", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("scored_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("skip_reason", sa.String(length=64), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("run_id"),
        sa.CheckConstraint(
            "gate_zone IN ('FULL_DEPLOY', 'REDUCED', 'DEFENSIVE')",
            name="signal_scanner_runs_zone_check",
        ),
    )
    op.create_index(
        "ix_signal_scanner_runs_date",
        "signal_scanner_runs",
        ["run_date"],
    )

    op.create_table(
        "signal_scanner_scores",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        # Raw factor values (units differ — captured for audit / debugging)
        sa.Column("mom_xover", sa.Numeric(12, 6), nullable=True),
        sa.Column("vol_surge", sa.Numeric(12, 6), nullable=True),
        sa.Column("rs_vs_spy", sa.Numeric(12, 6), nullable=True),
        sa.Column("high_52w_proximity", sa.Numeric(12, 6), nullable=True),
        sa.Column("short_interest_decline", sa.Numeric(12, 6), nullable=True),
        # Universe-relative percentiles (0-100)
        sa.Column("mom_xover_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("vol_surge_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("rs_vs_spy_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("high_52w_proximity_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("short_interest_decline_pct", sa.Numeric(6, 2), nullable=True),
        # Composite + rank
        sa.Column("composite_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("factor_coverage", sa.Numeric(4, 2), nullable=False),
        sa.PrimaryKeyConstraint("run_id", "symbol"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["signal_scanner_runs.run_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_signal_scanner_scores_symbol",
        "signal_scanner_scores",
        ["symbol", "run_id"],
    )
    op.create_index(
        "ix_signal_scanner_scores_rank",
        "signal_scanner_scores",
        ["run_id", "rank"],
    )


def downgrade() -> None:
    op.drop_index("ix_signal_scanner_scores_rank", table_name="signal_scanner_scores")
    op.drop_index("ix_signal_scanner_scores_symbol", table_name="signal_scanner_scores")
    op.drop_table("signal_scanner_scores")
    op.drop_index("ix_signal_scanner_runs_date", table_name="signal_scanner_runs")
    op.drop_table("signal_scanner_runs")
