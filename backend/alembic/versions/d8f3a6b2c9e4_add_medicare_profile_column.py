"""Medicare premium profile lever.

Monthly Medicare cost per covered member 65+ (Part B + Part D +
supplement, today's $). NULL means "use the published-rate default"
(CMS Part B $202.90 + Part D BBP $38.99 + KFF Plan G average $164 for
2026 — constants with sources in ``_aca_estimator``); an explicit 0
turns the line off. Retirement item D part (e).

Revision ID: d8f3a6b2c9e4
Revises: c7e9f2a4b8d3
Create Date: 2026-06-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8f3a6b2c9e4"
down_revision: str | None = "c7e9f2a4b8d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "household_profiles",
        sa.Column("medicare_monthly_per_person", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("household_profiles", "medicare_monthly_per_person")
