"""ACA healthcare-stream profile settings.

Three planner levers for the retirement ACA expense stream: metal tier
(silver benchmark default, bronze toggle, none to disable), an optional
manual age-21 premium override (wins over the CMS landscape anchors),
and the monthly out-of-pocket baseline (seeded from the deduped Money
spend derivation, user-editable).

Revision ID: c7e9f2a4b8d3
Revises: b3e8d2c7a9f1
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e9f2a4b8d3"
down_revision: str | None = "b3e8d2c7a9f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("household_profiles", sa.Column("aca_tier", sa.Text(), nullable=True))
    op.add_column(
        "household_profiles",
        sa.Column("aca_premium_age21_override", sa.Numeric(10, 2), nullable=True),
    )
    op.add_column(
        "household_profiles", sa.Column("aca_oop_monthly", sa.Numeric(10, 2), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("household_profiles", "aca_oop_monthly")
    op.drop_column("household_profiles", "aca_premium_age21_override")
    op.drop_column("household_profiles", "aca_tier")
