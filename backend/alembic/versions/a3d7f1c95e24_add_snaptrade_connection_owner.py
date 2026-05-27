"""add snaptrade connection owner attribution

Revision ID: a3d7f1c95e24
Revises: f2b3c4d5e6a7
Create Date: 2026-05-27 18:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3d7f1c95e24"
down_revision: str | Sequence[str] | None = "f2b3c4d5e6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add durable owner attribution to brokerage connections.

    These columns are intentionally NOT written by the connection upsert in
    the sync path, so a user's ownership choice (e.g. which login belongs to
    a spouse) persists across re-syncs. ``portfolio_accounts.is_spouse`` is
    derived from these via reconciliation: an account is spouse-owned only
    when every connection that surfaces it is spouse-owned, which keeps joint
    accounts (visible under both logins) attributed to the household.
    """
    op.add_column(
        "snaptrade_connections",
        sa.Column(
            "owner_is_spouse",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "snaptrade_connections",
        sa.Column("owner_name", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("snaptrade_connections", "owner_name")
    op.drop_column("snaptrade_connections", "owner_is_spouse")
