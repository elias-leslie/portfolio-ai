"""add ips_targets and ips_drift_history

Revision ID: 8a4e92c1d3f0
Revises: e055f9ddb756
Create Date: 2026-05-09 19:30:00.000000

F3 introduces the Investment Policy Statement (IPS) layer that the
DriftCalculator and RebalancePlanner depend on. Two tables:

- ips_targets: the user's allocation goals. ``scope`` lets the same
  table store household-wide goals and per-account overrides without
  a join. ``drift_band_pct`` is the +/- corridor before we flag the
  class as out-of-band. Unique on ``(scope, scope_id, asset_class)``.

- ips_drift_history: daily snapshots written by the
  ``portfolio-drift-snapshot`` Hatchet workflow (cron ``0 18 * * *``).
  Composite PK ``(scope, scope_id, asset_class, snapshot_date)`` so
  re-runs on the same day are idempotent and the trend chart query is
  index-only.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8a4e92c1d3f0"
down_revision: str | Sequence[str] | None = "e055f9ddb756"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ips_targets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("target_pct", sa.Numeric(6, 4), nullable=False),
        sa.Column(
            "drift_band_pct",
            sa.Numeric(6, 4),
            nullable=False,
            server_default=sa.text("0.05"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope", "scope_id", "asset_class", name="uq_ips_targets_scope_class"
        ),
        sa.CheckConstraint(
            "scope IN ('household','account')",
            name="ck_ips_targets_scope",
        ),
        sa.CheckConstraint(
            "target_pct >= 0 AND target_pct <= 1",
            name="ck_ips_targets_target_pct_range",
        ),
        sa.CheckConstraint(
            "drift_band_pct >= 0 AND drift_band_pct <= 1",
            name="ck_ips_targets_band_pct_range",
        ),
    )
    op.create_index(
        "ix_ips_targets_scope_id",
        "ips_targets",
        ["scope", "scope_id"],
    )

    op.create_table(
        "ips_drift_history",
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("scope_id", sa.String(length=64), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("target_pct", sa.Numeric(6, 4), nullable=False),
        sa.Column("actual_pct", sa.Numeric(6, 4), nullable=False),
        sa.Column("drift_pct", sa.Numeric(8, 6), nullable=False),
        sa.Column("total_value", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "scope", "scope_id", "asset_class", "snapshot_date",
            name="pk_ips_drift_history",
        ),
    )
    op.create_index(
        "ix_ips_drift_history_snapshot_date",
        "ips_drift_history",
        [sa.text("snapshot_date DESC")],
    )
    op.create_index(
        "ix_ips_drift_history_scope_id",
        "ips_drift_history",
        ["scope", "scope_id", "snapshot_date"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ips_drift_history_scope_id", table_name="ips_drift_history")
    op.drop_index("ix_ips_drift_history_snapshot_date", table_name="ips_drift_history")
    op.drop_table("ips_drift_history")
    op.drop_index("ix_ips_targets_scope_id", table_name="ips_targets")
    op.drop_table("ips_targets")
