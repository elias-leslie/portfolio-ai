"""add match_key to household tracked accounts

Revision ID: 6b2a76a1d9f1
Revises: 4d7d4a8cc18a
Create Date: 2026-04-13 21:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b2a76a1d9f1"
down_revision: str | Sequence[str] | None = "4d7d4a8cc18a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "household_tracked_accounts",
        sa.Column("match_key", sa.String(length=512), nullable=True),
    )
    op.create_index(
        "uq_household_tracked_accounts_match_key",
        "household_tracked_accounts",
        ["match_key"],
        unique=True,
        postgresql_where=sa.text("match_key IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_household_tracked_accounts_match_key",
        table_name="household_tracked_accounts",
    )
    op.drop_column("household_tracked_accounts", "match_key")
