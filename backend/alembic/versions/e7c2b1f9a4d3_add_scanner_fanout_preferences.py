"""add scanner_fanout preference overrides

Revision ID: e7c2b1f9a4d3
Revises: fc8b4e7a9d31
Create Date: 2026-05-18 23:30:00.000000

Master toggle + four numeric knobs for the L3 committee fan-out. All
columns are nullable so existing rows stay valid; the service layer
falls back to env vars (then hard-coded defaults) when a value is NULL.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7c2b1f9a4d3"
down_revision: str | Sequence[str] | None = "fc8b4e7a9d31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "automation_preferences",
        sa.Column("scanner_fanout_enabled", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "automation_preferences",
        sa.Column("scanner_fanout_top_n", sa.Integer(), nullable=True),
    )
    op.add_column(
        "automation_preferences",
        sa.Column("scanner_fanout_tier1_keep", sa.Integer(), nullable=True),
    )
    op.add_column(
        "automation_preferences",
        sa.Column("scanner_fanout_max_daily", sa.Integer(), nullable=True),
    )
    op.add_column(
        "automation_preferences",
        sa.Column("scanner_fanout_cache_ttl_hours", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("automation_preferences", "scanner_fanout_cache_ttl_hours")
    op.drop_column("automation_preferences", "scanner_fanout_max_daily")
    op.drop_column("automation_preferences", "scanner_fanout_tier1_keep")
    op.drop_column("automation_preferences", "scanner_fanout_top_n")
    op.drop_column("automation_preferences", "scanner_fanout_enabled")
