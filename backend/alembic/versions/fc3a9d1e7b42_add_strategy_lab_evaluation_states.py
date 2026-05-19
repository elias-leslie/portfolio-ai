"""add strategy lab evaluation states

Revision ID: fc3a9d1e7b42
Revises: fb1a4c8d6e92
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "fc3a9d1e7b42"
down_revision: str | Sequence[str] | None = "fb1a4c8d6e92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "strategy_lab_evaluation_states",
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("strategy_type", sa.String(length=32), nullable=False),
        sa.Column("previous_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("current_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_transition", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_strategy_lab_states_symbol", "strategy_lab_evaluation_states", ["symbol"])
    op.create_index("ix_strategy_lab_states_evaluated_at", "strategy_lab_evaluation_states", ["last_evaluated_at"])


def downgrade() -> None:
    op.drop_index("ix_strategy_lab_states_evaluated_at", table_name="strategy_lab_evaluation_states")
    op.drop_index("ix_strategy_lab_states_symbol", table_name="strategy_lab_evaluation_states")
    op.drop_table("strategy_lab_evaluation_states")
