"""prevent negative remaining shares in portfolio tax lots

Revision ID: f4a5b6c7d8e9
Revises: f825742b0001
Create Date: 2026-07-12 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f4a5b6c7d8e9"
down_revision: str | Sequence[str] | None = "f825742b0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT_NAME = "ck_portfolio_tax_lots_remaining_shares_nonnegative"


def upgrade() -> None:
    """Reject corrupt lot mutations at the database boundary."""
    op.create_check_constraint(
        _CONSTRAINT_NAME,
        "portfolio_tax_lots",
        "remaining_shares >= 0",
    )


def downgrade() -> None:
    """Remove the nonnegative remaining-shares guard."""
    op.drop_constraint(
        _CONSTRAINT_NAME,
        "portfolio_tax_lots",
        type_="check",
    )
