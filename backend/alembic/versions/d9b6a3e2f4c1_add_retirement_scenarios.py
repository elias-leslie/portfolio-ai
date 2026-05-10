"""add retirement_scenarios

Revision ID: d9b6a3e2f4c1
Revises: c8d4f1a3b6e2
Create Date: 2026-05-09 22:00:00.000000

F5 introduces user-initiated retirement Monte Carlo / financial-plan
projections. Distinct from ``backend/app/backtest/monte_carlo.py``
(trade-return stress, not life-goal). The scenario row stores the full
input snapshot and result summary so the UI / agent can compare runs
without re-simulating; ``cma_source`` stamps the long-term return
estimates version (e.g. ``yaml-v1``) so v2 FRED-derived runs are easy
to filter.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d9b6a3e2f4c1"
down_revision: str | Sequence[str] | None = "c8d4f1a3b6e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "retirement_scenarios",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("household_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "inputs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "results",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("cma_source", sa.String(length=64), nullable=False),
        sa.Column("trial_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "trial_count > 0 AND trial_count <= 50000",
            name="ck_retirement_scenarios_trial_count_range",
        ),
    )
    op.create_index(
        "ix_retirement_scenarios_household_created",
        "retirement_scenarios",
        ["household_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_retirement_scenarios_household_created",
        table_name="retirement_scenarios",
    )
    op.drop_table("retirement_scenarios")
