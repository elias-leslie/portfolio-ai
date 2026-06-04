"""Add scheduled account-sync automation preference.

Revision ID: c1a2b3d4e5f6
Revises: bc74e8f0a9d1
Create Date: 2026-06-01 22:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c1a2b3d4e5f6"
down_revision = "bc74e8f0a9d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "automation_preferences",
        sa.Column("scheduled_account_sync_enabled", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("automation_preferences", "scheduled_account_sync_enabled")
