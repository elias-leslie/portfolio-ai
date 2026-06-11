"""Allocation scenarios + bridge growth mode.

Named what-if allocation scenarios (symbol/weight lists with optional
bridge overrides) persist so the retirement allocation lab can compare
the real account-derived allocation against user-defined mixes. The
bridge sleeve gains a growth mode: ``fixed`` keeps the deterministic
real_return, ``portfolio`` lets the sleeve ride the simulated portfolio
returns (volatility and sequence risk included).

Revision ID: f2b8d3e9a1c5
Revises: d9e3a6b8c2f4
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2b8d3e9a1c5"
down_revision: str | None = "d9e3a6b8c2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("household_profiles", sa.Column("bridge_growth", sa.Text(), nullable=True))
    op.create_table(
        "household_retirement_allocation_scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("holdings", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("bridge_growth", sa.Text(), nullable=True),
        sa.Column("bridge_real_return", sa.Numeric(6, 5), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(
        "idx_household_retirement_allocation_scenarios_updated_at",
        "household_retirement_allocation_scenarios",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "idx_household_retirement_allocation_scenarios_updated_at",
        table_name="household_retirement_allocation_scenarios",
    )
    op.drop_table("household_retirement_allocation_scenarios")
    op.drop_column("household_profiles", "bridge_growth")
