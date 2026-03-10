"""add automation preference overrides

Revision ID: 10b1de025fa4
Revises: 4af7233ad813
Create Date: 2026-03-10 11:42:54.815482

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '10b1de025fa4'
down_revision: str | Sequence[str] | None = '4af7233ad813'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "automation_preferences",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("thesis_generation_enabled", sa.Boolean(), nullable=True),
        sa.Column("auto_remove_on_invalidation", sa.Boolean(), nullable=True),
        sa.Column("auto_trim_enabled", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("automation_preferences")
