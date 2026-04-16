"""Add agentic background workload preference overrides.

Revision ID: 1a2b3c4d5e6f
Revises: d4b6e7f8a9c1
Create Date: 2026-04-16 18:05:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "1a2b3c4d5e6f"
down_revision = "d4b6e7f8a9c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "automation_preferences",
        sa.Column("scheduled_jenny_operator_enabled", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "automation_preferences",
        sa.Column("scheduled_ml_labeling_enabled", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("automation_preferences", "scheduled_ml_labeling_enabled")
    op.drop_column("automation_preferences", "scheduled_jenny_operator_enabled")
