"""add jenny operator tables

Revision ID: 9ea9667630c4
Revises: a1b2c3d4e5f6
Create Date: 2026-03-07 10:08:29.187282

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9ea9667630c4"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Jenny operator tables for routines, notifications, and learning."""
    op.create_table(
        "jenny_routines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("routine_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("triggered_by", sa.Text(), nullable=False, server_default=sa.text("'system'")),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("agents_used", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("symbols_scanned", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("notifications_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_jenny_routines_type", "jenny_routines", ["routine_type"])
    op.create_index("idx_jenny_routines_status", "jenny_routines", ["status"])
    op.create_index("idx_jenny_routines_started_at", "jenny_routines", ["started_at"])

    op.create_table(
        "jenny_agent_evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("routine_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jenny_routines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.Text(), sa.ForeignKey("symbols.symbol", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("verdict", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("strengths", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("weaknesses", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("thesis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("watchlist_thesis.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent_run_id", sa.Text(), sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_jenny_evals_routine_id", "jenny_agent_evaluations", ["routine_id"])
    op.create_index("idx_jenny_evals_symbol", "jenny_agent_evaluations", ["symbol"])
    op.create_index("idx_jenny_evals_agent_name", "jenny_agent_evaluations", ["agent_name"])
    op.create_index("idx_jenny_evals_created_at", "jenny_agent_evaluations", ["created_at"])

    op.create_table(
        "jenny_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("routine_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jenny_routines.id", ondelete="SET NULL"), nullable=True),
        sa.Column("symbol", sa.Text(), sa.ForeignKey("symbols.symbol", ondelete="SET NULL"), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_jenny_notifications_status", "jenny_notifications", ["status"])
    op.create_index("idx_jenny_notifications_severity", "jenny_notifications", ["severity"])
    op.create_index("idx_jenny_notifications_symbol", "jenny_notifications", ["symbol"])
    op.create_index("idx_jenny_notifications_created_at", "jenny_notifications", ["created_at"])

    op.create_table(
        "jenny_trade_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("symbol", sa.Text(), sa.ForeignKey("symbols.symbol", ondelete="CASCADE"), nullable=False),
        sa.Column("thesis_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("watchlist_thesis.id", ondelete="SET NULL"), nullable=True),
        sa.Column("idea_id", sa.Text(), sa.ForeignKey("idea_outcomes.idea_id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_source", sa.Text(), nullable=False),
        sa.Column("outcome_label", sa.Text(), nullable=False),
        sa.Column("return_pct", sa.Float(), nullable=True),
        sa.Column("lesson", sa.Text(), nullable=False),
        sa.Column("what_worked", sa.Text(), nullable=True),
        sa.Column("what_failed", sa.Text(), nullable=True),
        sa.Column("next_time", sa.Text(), nullable=True),
        sa.Column("agent_consensus", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_jenny_trade_reviews_symbol", "jenny_trade_reviews", ["symbol"])
    op.create_index("idx_jenny_trade_reviews_created_at", "jenny_trade_reviews", ["created_at"])
    op.create_index("idx_jenny_trade_reviews_idea_id", "jenny_trade_reviews", ["idea_id"])

    op.create_table(
        "jenny_agent_scorecards",
        sa.Column("agent_name", sa.Text(), primary_key=True, nullable=False),
        sa.Column("total_evaluations", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completed_reviews", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("positive_verdicts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("avg_return_pct", sa.Float(), nullable=True),
        sa.Column("agreement_rate", sa.Float(), nullable=True),
        sa.Column("calibration_score", sa.Float(), nullable=True),
        sa.Column("strengths", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("weaknesses", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("last_evaluation_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    """Drop Jenny operator tables."""
    op.drop_table("jenny_agent_scorecards")
    op.drop_index("idx_jenny_trade_reviews_idea_id", table_name="jenny_trade_reviews")
    op.drop_index("idx_jenny_trade_reviews_created_at", table_name="jenny_trade_reviews")
    op.drop_index("idx_jenny_trade_reviews_symbol", table_name="jenny_trade_reviews")
    op.drop_table("jenny_trade_reviews")
    op.drop_index("idx_jenny_notifications_created_at", table_name="jenny_notifications")
    op.drop_index("idx_jenny_notifications_symbol", table_name="jenny_notifications")
    op.drop_index("idx_jenny_notifications_severity", table_name="jenny_notifications")
    op.drop_index("idx_jenny_notifications_status", table_name="jenny_notifications")
    op.drop_table("jenny_notifications")
    op.drop_index("idx_jenny_evals_created_at", table_name="jenny_agent_evaluations")
    op.drop_index("idx_jenny_evals_agent_name", table_name="jenny_agent_evaluations")
    op.drop_index("idx_jenny_evals_symbol", table_name="jenny_agent_evaluations")
    op.drop_index("idx_jenny_evals_routine_id", table_name="jenny_agent_evaluations")
    op.drop_table("jenny_agent_evaluations")
    op.drop_index("idx_jenny_routines_started_at", table_name="jenny_routines")
    op.drop_index("idx_jenny_routines_status", table_name="jenny_routines")
    op.drop_index("idx_jenny_routines_type", table_name="jenny_routines")
    op.drop_table("jenny_routines")
