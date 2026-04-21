"""add market prediction committee tables

Revision ID: 6f3b1c2d4e5f
Revises: 2b3c4d5e6f70
Create Date: 2026-04-20 22:28:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "6f3b1c2d4e5f"
down_revision: str | Sequence[str] | None = "2b3c4d5e6f70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    """Create market prediction committee persistence tables."""
    op.create_table(
        "market_prediction_runs",
        sa.Column("id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("as_of_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("base_date", sa.Date(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("target_universe", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("lead_symbol", sa.Text(), nullable=False),
        sa.Column("lead_direction", sa.Text(), nullable=False),
        sa.Column("lead_prob_up", sa.Float(), nullable=True),
        sa.Column("lead_expected_move_pct", sa.Float(), nullable=True),
        sa.Column("source_snapshot", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("committee_summary", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index(
        "idx_market_prediction_runs_window_asof",
        "market_prediction_runs",
        ["window_days", "as_of_ts"],
    )
    op.create_index(
        "idx_market_prediction_runs_target_date",
        "market_prediction_runs",
        ["target_date"],
    )

    op.create_table(
        "market_prediction_calls",
        sa.Column("id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("run_id", sa.Text(), sa.ForeignKey("market_prediction_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("direction_label", sa.Text(), nullable=False),
        sa.Column("prob_up", sa.Float(), nullable=False),
        sa.Column("expected_move_pct", sa.Float(), nullable=False),
        sa.Column("confidence_band_low_pct", sa.Float(), nullable=True),
        sa.Column("confidence_band_high_pct", sa.Float(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("committee_disagreement_score", sa.Float(), nullable=True),
        sa.Column("rationale_summary", sa.Text(), nullable=True),
        sa.Column("top_source_clusters", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("run_id", "symbol", name="uq_market_prediction_calls_run_symbol"),
    )
    op.create_index(
        "idx_market_prediction_calls_symbol_window",
        "market_prediction_calls",
        ["symbol", "window_days"],
    )

    op.create_table(
        "market_prediction_votes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Text(), sa.ForeignKey("market_prediction_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("seat_key", sa.Text(), nullable=False),
        sa.Column("agent_slug", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("direction_label", sa.Text(), nullable=False),
        sa.Column("prob_up", sa.Float(), nullable=False),
        sa.Column("expected_move_pct", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("rationale_summary", sa.Text(), nullable=True),
        sa.Column("source_clusters", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index(
        "idx_market_prediction_votes_run_seat_symbol",
        "market_prediction_votes",
        ["run_id", "seat_key", "symbol"],
    )

    op.create_table(
        "market_prediction_evaluations",
        sa.Column("call_id", sa.Text(), sa.ForeignKey("market_prediction_calls.id", ondelete="CASCADE"), primary_key=True, nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("base_close", sa.Float(), nullable=False),
        sa.Column("target_close", sa.Float(), nullable=False),
        sa.Column("realized_move_pct", sa.Float(), nullable=False),
        sa.Column("direction_hit", sa.Boolean(), nullable=False),
        sa.Column("move_abs_error_pct", sa.Float(), nullable=False),
        sa.Column("brier_score", sa.Float(), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index(
        "idx_market_prediction_evaluations_evaluated_at",
        "market_prediction_evaluations",
        ["evaluated_at"],
    )


def downgrade() -> None:
    """Drop market prediction committee persistence tables."""
    op.drop_index(
        "idx_market_prediction_evaluations_evaluated_at",
        table_name="market_prediction_evaluations",
    )
    op.drop_table("market_prediction_evaluations")
    op.drop_index(
        "idx_market_prediction_votes_run_seat_symbol",
        table_name="market_prediction_votes",
    )
    op.drop_table("market_prediction_votes")
    op.drop_index(
        "idx_market_prediction_calls_symbol_window",
        table_name="market_prediction_calls",
    )
    op.drop_table("market_prediction_calls")
    op.drop_index(
        "idx_market_prediction_runs_target_date",
        table_name="market_prediction_runs",
    )
    op.drop_index(
        "idx_market_prediction_runs_window_asof",
        table_name="market_prediction_runs",
    )
    op.drop_table("market_prediction_runs")
