"""add signal_macro_snapshots

Revision ID: f9d2e5a8b3c1
Revises: f8c9d1e4a2b7
Create Date: 2026-05-17 17:30:00.000000

Daily output of the L1 macro deployment gate: six raw signals, six 0-100
normalised scores, a weighted composite, and a discrete zone label
(FULL_DEPLOY / REDUCED / DEFENSIVE). Persisted at trading-day granularity
so the L2 scanner and L3 committee fan-out can branch on yesterday's gate
and so walk-forward replays can reconstruct what the system would have
decided in the past.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f9d2e5a8b3c1"
down_revision: str | Sequence[str] | None = "f8c9d1e4a2b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signal_macro_snapshots",
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        # Raw signal values (units differ — captured for audit / debugging)
        sa.Column("vix_close", sa.Numeric(10, 4), nullable=True),
        sa.Column("term_spread_bps", sa.Numeric(10, 2), nullable=True),
        sa.Column("breadth_pct", sa.Numeric(6, 2), nullable=True),
        sa.Column("hy_spread", sa.Numeric(8, 4), nullable=True),
        sa.Column("put_call_ratio", sa.Numeric(6, 4), nullable=True),
        sa.Column("factor_crowding_corr", sa.Numeric(6, 4), nullable=True),
        # Normalised 0-100 component scores
        sa.Column("vix_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("term_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("breadth_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("credit_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("putcall_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("crowding_score", sa.Numeric(6, 2), nullable=True),
        # Composite + zone
        sa.Column("deployment_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("zone", sa.String(length=16), nullable=False),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("snapshot_date"),
        sa.CheckConstraint(
            "zone IN ('FULL_DEPLOY', 'REDUCED', 'DEFENSIVE')",
            name="signal_macro_snapshots_zone_check",
        ),
    )
    op.create_index(
        "ix_signal_macro_snapshots_zone",
        "signal_macro_snapshots",
        ["zone", "snapshot_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_signal_macro_snapshots_zone", table_name="signal_macro_snapshots")
    op.drop_table("signal_macro_snapshots")
