"""add household tracked accounts

Revision ID: b917dfebe69d
Revises: e528b11bec24
Create Date: 2026-04-09 22:45:25.069323

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b917dfebe69d'
down_revision: str | Sequence[str] | None = 'e528b11bec24'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "household_tracked_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("asset_group", sa.String(length=32), nullable=False),
        sa.Column("account_type", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("institution_name", sa.String(length=255), nullable=True),
        sa.Column("owner_name", sa.String(length=255), nullable=True),
        sa.Column("account_mask", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_household_tracked_accounts_asset_group",
        "household_tracked_accounts",
        ["asset_group"],
        unique=False,
    )
    op.create_index(
        "idx_household_tracked_accounts_updated_at",
        "household_tracked_accounts",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "idx_household_tracked_accounts_updated_at",
        table_name="household_tracked_accounts",
    )
    op.drop_index(
        "idx_household_tracked_accounts_asset_group",
        table_name="household_tracked_accounts",
    )
    op.drop_table("household_tracked_accounts")
