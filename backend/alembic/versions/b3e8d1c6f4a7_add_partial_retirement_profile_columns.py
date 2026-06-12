"""Partial-retirement window profile levers.

Primary retired, spouse still working: spouse net take-home ($/mo,
gates the feature — NULL = off), window spending override ($/mo, NULL
falls back to annual_expenses/12), and spouse gross annual wages ($/yr,
stacks the tax brackets without charging her wage tax to the
portfolio). All REAL (today's) dollars.

Revision ID: b3e8d1c6f4a7
Revises: a9c4e7f2b1d8
Create Date: 2026-06-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3e8d1c6f4a7"
down_revision: str | None = "a9c4e7f2b1d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "household_profiles",
        sa.Column("spouse_net_monthly_income", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "household_profiles",
        sa.Column("partial_retirement_monthly_spend", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "household_profiles",
        sa.Column("spouse_gross_annual_income", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("household_profiles", "spouse_gross_annual_income")
    op.drop_column("household_profiles", "partial_retirement_monthly_spend")
    op.drop_column("household_profiles", "spouse_net_monthly_income")
