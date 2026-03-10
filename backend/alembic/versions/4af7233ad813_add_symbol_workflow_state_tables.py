"""add symbol workflow state tables

Revision ID: 4af7233ad813
Revises: c1b476112bf4
Create Date: 2026-03-10 11:07:58.761982

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4af7233ad813'
down_revision: str | Sequence[str] | None = 'c1b476112bf4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "symbol_workflows",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("current_stage", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=False, server_default="system"),
        sa.Column("last_transition_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.CheckConstraint(
            "current_stage IN ('discover', 'thesis_ready', 'tracked', 'live', 'review_due', 'invalidated', 'exited')",
            name="ck_symbol_workflows_stage",
        ),
        sa.ForeignKeyConstraint(["symbol"], ["symbols.symbol"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("symbol"),
    )
    op.create_index(
        "idx_symbol_workflows_stage_transition",
        "symbol_workflows",
        ["current_stage", "last_transition_at"],
        unique=False,
    )

    op.create_table(
        "symbol_workflow_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("from_stage", sa.Text(), nullable=True),
        sa.Column("to_stage", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.CheckConstraint(
            "to_stage IN ('discover', 'thesis_ready', 'tracked', 'live', 'review_due', 'invalidated', 'exited')",
            name="ck_symbol_workflow_events_to_stage",
        ),
        sa.ForeignKeyConstraint(["symbol"], ["symbol_workflows.symbol"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_symbol_workflow_events_symbol_created",
        "symbol_workflow_events",
        ["symbol", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_symbol_workflow_events_symbol_created", table_name="symbol_workflow_events")
    op.drop_table("symbol_workflow_events")
    op.drop_index("idx_symbol_workflows_stage_transition", table_name="symbol_workflows")
    op.drop_table("symbol_workflows")
