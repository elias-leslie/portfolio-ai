"""add market prediction vote eval and seat review tables

Revision ID: 8ac0f7d9e1b2
Revises: 6f3b1c2d4e5f
Create Date: 2026-04-22 15:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8ac0f7d9e1b2"
down_revision: str | Sequence[str] | None = "6f3b1c2d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
SUPPORTED_WINDOWS = (1, 3, 7, 14)



def upgrade() -> None:
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



def downgrade() -> None:
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
