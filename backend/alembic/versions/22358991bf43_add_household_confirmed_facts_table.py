"""add household_confirmed_facts table

Revision ID: 22358991bf43
Revises: 5f4a1c6d9e72
Create Date: 2026-03-11 16:13:36.903372

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '22358991bf43'
down_revision: str | Sequence[str] | None = '5f4a1c6d9e72'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "household_confirmed_facts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("fact_key", sa.Text(), nullable=False),
        sa.Column("fact_value", sa.Text(), nullable=False),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("metadata", sa.JSON(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fact_key"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("household_confirmed_facts")
