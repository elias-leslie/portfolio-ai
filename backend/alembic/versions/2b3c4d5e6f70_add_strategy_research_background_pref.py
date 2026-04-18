"""Add strategy research background preference override.

Revision ID: 2b3c4d5e6f70
Revises: 1a2b3c4d5e6f
Create Date: 2026-04-16 18:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "2b3c4d5e6f70"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "automation_preferences",
        sa.Column("scheduled_strategy_research_enabled", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("automation_preferences", "scheduled_strategy_research_enabled")
