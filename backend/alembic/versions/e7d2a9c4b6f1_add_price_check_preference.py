"""Add scheduled_price_check_enabled to automation_preferences.

Revision ID: e7d2a9c4b6f1
Revises: b3e8d1c6f4a7
Create Date: 2026-06-12 21:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7d2a9c4b6f1"
down_revision: str | Sequence[str] | None = "b3e8d1c6f4a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "automation_preferences",
        sa.Column("scheduled_price_check_enabled", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("automation_preferences", "scheduled_price_check_enabled")
