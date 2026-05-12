"""drop market pulse research tracking

Revision ID: e2b9c7a4d8f1
Revises: d6e1c8a2f3b4
Create Date: 2026-05-12 00:25:00.000000

The Today page's Market Pulse panel and its `HomeTodayBriefService` +
`MarketPulseResearchService` were removed in favor of live market data
and the upcoming Investment Committee. These two tables were the
research-tracking ledger for that single-agent narrative service and
have no remaining consumers.

Drop mirrors the inverse of ``d4b6e7f8a9c1_add_market_pulse_research_tracking.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e2b9c7a4d8f1"
down_revision: str | Sequence[str] | None = "d6e1c8a2f3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop market pulse research tracking tables."""
    op.drop_index(
        "idx_market_pulse_source_profiles_score",
        table_name="market_pulse_source_profiles",
    )
    op.drop_index(
        "idx_market_pulse_source_profiles_validation_status",
        table_name="market_pulse_source_profiles",
    )
    op.drop_index(
        "idx_market_pulse_source_profiles_domain",
        table_name="market_pulse_source_profiles",
    )
    op.drop_table("market_pulse_source_profiles")
    op.drop_index(
        "idx_market_pulse_research_runs_request_kind",
        table_name="market_pulse_research_runs",
    )
    op.drop_index(
        "idx_market_pulse_research_runs_status",
        table_name="market_pulse_research_runs",
    )
    op.drop_index(
        "idx_market_pulse_research_runs_created_at",
        table_name="market_pulse_research_runs",
    )
    op.drop_table("market_pulse_research_runs")


def downgrade() -> None:
    """Recreate market pulse research tracking tables."""
    op.create_table(
        "market_pulse_research_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("request_kind", sa.Text(), nullable=False),
        sa.Column("cache_key", sa.Text(), nullable=True),
        sa.Column(
            "fallback_used",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_market_pulse_research_runs_created_at",
        "market_pulse_research_runs",
        ["created_at"],
    )
    op.create_index(
        "idx_market_pulse_research_runs_status",
        "market_pulse_research_runs",
        ["status"],
    )
    op.create_index(
        "idx_market_pulse_research_runs_request_kind",
        "market_pulse_research_runs",
        ["request_kind"],
    )

    op.create_table(
        "market_pulse_source_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("source_signal_tier", sa.Text(), nullable=False),
        sa.Column(
            "decision_value_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "validation_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("url", name="uq_market_pulse_source_profiles_url"),
    )
    op.create_index(
        "idx_market_pulse_source_profiles_domain",
        "market_pulse_source_profiles",
        ["domain"],
    )
    op.create_index(
        "idx_market_pulse_source_profiles_validation_status",
        "market_pulse_source_profiles",
        ["validation_status"],
    )
    op.create_index(
        "idx_market_pulse_source_profiles_score",
        "market_pulse_source_profiles",
        ["decision_value_score"],
    )
