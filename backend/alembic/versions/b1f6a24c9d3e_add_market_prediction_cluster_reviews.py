"""add market prediction cluster review table

Revision ID: b1f6a24c9d3e
Revises: 8ac0f7d9e1b2
Create Date: 2026-04-22 17:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b1f6a24c9d3e"
down_revision: str | Sequence[str] | None = "8ac0f7d9e1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB(astext_type=sa.Text())
SUPPORTED_WINDOWS = (1, 3, 7, 14)



def upgrade() -> None:
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



def downgrade() -> None:
    op.drop_index(
        "idx_market_prediction_cluster_reviews_window_generated",
        table_name="market_prediction_cluster_reviews",
    )
    op.drop_table("market_prediction_cluster_reviews")
