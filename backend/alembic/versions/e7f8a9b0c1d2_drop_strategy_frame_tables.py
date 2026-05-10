"""drop strategy frame tables

Revision ID: e7f8a9b0c1d2
Revises: d3a5b7c9e1f4
Create Date: 2026-05-10 19:30:00.000000

Drops the 9 tables that backed the short-term strategy lab frame:
strategy_definitions, strategy_lineage, strategy_metrics, strategy_performance,
strategy_reviews, strategy_screening_results, strategy_seeds, strategy_signals,
plus benchmark_comparisons. Project pivoted away from per-strategy backtesting
toward a company-fitness catalog driven by fundamentals + LLM committee, so
this lifecycle storage is no longer load-bearing.

The downgrade re-creates only the table shells (no data, no indexes beyond
primary keys) so historical migrations remain replayable on a fresh database.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7f8a9b0c1d2"
down_revision: str | Sequence[str] | None = "d3a5b7c9e1f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLES_TO_DROP = (
    "benchmark_comparisons",
    "strategy_screening_results",
    "strategy_signals",
    "strategy_reviews",
    "strategy_metrics",
    "strategy_performance",
    "strategy_lineage",
    "strategy_seeds",
    "strategy_definitions",
)


def upgrade() -> None:
    for table_name in _TABLES_TO_DROP:
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")


def downgrade() -> None:
    op.create_table(
        "strategy_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "strategy_seeds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "strategy_lineage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "strategy_performance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "strategy_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "strategy_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "strategy_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "strategy_screening_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "benchmark_comparisons",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
