"""drop market prediction tables

Revision ID: f3c5d8a1b9e7
Revises: e2b9c7a4d8f1
Create Date: 2026-05-12 02:00:00.000000

The legacy market-prediction committee (``market_prediction_*`` services,
router, model, repository) has been removed in favor of the Investment
Committee (``committee_*`` tables). This migration drops the seven
``market_prediction_*`` tables that backed the deleted code:

    - ``market_prediction_runs``
    - ``market_prediction_calls``
    - ``market_prediction_votes``
    - ``market_prediction_evaluations``
    - ``market_prediction_vote_evaluations``
    - ``market_prediction_seat_reviews``
    - ``market_prediction_cluster_reviews``

Drop order respects the FK chain (calls/votes/evaluations -> runs;
vote_evaluations -> votes). Downgrade re-creates them by inverting the
three forward migrations:
``6f3b1c2d4e5f_add_market_prediction_tables``,
``8ac0f7d9e1b2_add_market_prediction_vote_eval_and_seat_review_tables``,
``b1f6a24c9d3e_add_market_prediction_cluster_reviews``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f3c5d8a1b9e7"
down_revision: str | Sequence[str] | None = "e2b9c7a4d8f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


JSONB = postgresql.JSONB(astext_type=sa.Text())
SUPPORTED_WINDOWS = (1, 3, 7, 14)


def upgrade() -> None:
    """Drop legacy market_prediction_* tables."""
    op.drop_index(
        "idx_market_prediction_cluster_reviews_window_generated",
        table_name="market_prediction_cluster_reviews",
    )
    op.drop_table("market_prediction_cluster_reviews")

    op.drop_index(
        "idx_market_prediction_seat_reviews_window_generated",
        table_name="market_prediction_seat_reviews",
    )
    op.drop_table("market_prediction_seat_reviews")

    op.drop_index(
        "idx_market_prediction_vote_evaluations_symbol_window_evaluated",
        table_name="market_prediction_vote_evaluations",
    )
    op.drop_index(
        "idx_market_prediction_vote_evaluations_window_seat_evaluated",
        table_name="market_prediction_vote_evaluations",
    )
    op.drop_table("market_prediction_vote_evaluations")

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


def downgrade() -> None:
    """Recreate the legacy market_prediction_* tables."""
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

    op.create_table(
        "market_prediction_vote_evaluations",
        sa.Column(
            "vote_id",
            sa.Integer(),
            sa.ForeignKey("market_prediction_votes.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("seat_key", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("base_close", sa.Float(), nullable=False),
        sa.Column("target_close", sa.Float(), nullable=False),
        sa.Column("realized_move_pct", sa.Float(), nullable=False),
        sa.Column("direction_hit", sa.Boolean(), nullable=False),
        sa.Column("move_abs_error_pct", sa.Float(), nullable=False),
        sa.Column("brier_score", sa.Float(), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(
            f"window_days IN {SUPPORTED_WINDOWS}",
            name="ck_market_prediction_vote_evaluations_window_days",
        ),
    )
    op.execute(
        """
        CREATE INDEX idx_market_prediction_vote_evaluations_window_seat_evaluated
        ON market_prediction_vote_evaluations (window_days, seat_key, evaluated_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_market_prediction_vote_evaluations_symbol_window_evaluated
        ON market_prediction_vote_evaluations (symbol, window_days, evaluated_at DESC)
        """
    )

    op.create_table(
        "market_prediction_seat_reviews",
        sa.Column("id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("as_of_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("review_state", sa.Text(), nullable=False),
        sa.Column("seat_scorecards", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("review_summary", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(
            f"window_days IN {SUPPORTED_WINDOWS}",
            name="ck_market_prediction_seat_reviews_window_days",
        ),
        sa.CheckConstraint(
            "review_state IN ('live', 'warmup', 'degraded')",
            name="ck_market_prediction_seat_reviews_review_state",
        ),
        sa.UniqueConstraint("window_days", "as_of_ts", name="uq_market_prediction_seat_reviews_window_asof"),
    )
    op.create_index(
        "idx_market_prediction_seat_reviews_window_generated",
        "market_prediction_seat_reviews",
        ["window_days", sa.text("generated_at DESC")],
    )

    op.create_table(
        "market_prediction_cluster_reviews",
        sa.Column("id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("as_of_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("review_state", sa.Text(), nullable=False),
        sa.Column("cluster_scorecards", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("review_summary", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(
            f"window_days IN {SUPPORTED_WINDOWS}",
            name="ck_market_prediction_cluster_reviews_window_days",
        ),
        sa.CheckConstraint(
            "review_state IN ('live', 'warmup', 'degraded')",
            name="ck_market_prediction_cluster_reviews_review_state",
        ),
        sa.UniqueConstraint("window_days", "as_of_ts", name="uq_market_prediction_cluster_reviews_window_asof"),
    )
    op.create_index(
        "idx_market_prediction_cluster_reviews_window_generated",
        "market_prediction_cluster_reviews",
        ["window_days", sa.text("generated_at DESC")],
    )
