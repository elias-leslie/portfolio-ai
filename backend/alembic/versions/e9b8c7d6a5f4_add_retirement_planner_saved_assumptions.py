"""add retirement planner saved assumptions

Revision ID: e9b8c7d6a5f4
Revises: e7c2b1f9a4d3
Create Date: 2026-05-26 03:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e9b8c7d6a5f4"
down_revision: str | Sequence[str] | None = "e7c2b1f9a4d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("household_profiles", sa.Column("retirement_inflation_rate", sa.Numeric(8, 5), nullable=True))
    op.add_column("household_profiles", sa.Column("retirement_horizon_years", sa.Integer(), nullable=True))
    op.add_column("household_profiles", sa.Column("primary_social_security_monthly", sa.Numeric(12, 2), nullable=True))
    op.add_column("household_profiles", sa.Column("spouse_social_security_monthly", sa.Numeric(12, 2), nullable=True))
    op.add_column("household_profiles", sa.Column("primary_social_security_annual_earnings", sa.Numeric(12, 2), nullable=True))
    op.add_column("household_profiles", sa.Column("spouse_social_security_annual_earnings", sa.Numeric(12, 2), nullable=True))
    op.add_column("household_profiles", sa.Column("primary_social_security_start_age", sa.Integer(), nullable=True))
    op.add_column("household_profiles", sa.Column("spouse_social_security_start_age", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("household_profiles", "spouse_social_security_start_age")
    op.drop_column("household_profiles", "primary_social_security_start_age")
    op.drop_column("household_profiles", "spouse_social_security_annual_earnings")
    op.drop_column("household_profiles", "primary_social_security_annual_earnings")
    op.drop_column("household_profiles", "spouse_social_security_monthly")
    op.drop_column("household_profiles", "primary_social_security_monthly")
    op.drop_column("household_profiles", "retirement_horizon_years")
    op.drop_column("household_profiles", "retirement_inflation_rate")
