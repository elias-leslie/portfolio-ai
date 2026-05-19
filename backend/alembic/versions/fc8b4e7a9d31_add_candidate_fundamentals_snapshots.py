"""add candidate_fundamentals_snapshots + committee_runs.blended_rank

Revision ID: fc8b4e7a9d31
Revises: fb1a4c8d6e92
Create Date: 2026-05-18 22:00:00.000000

L3 alignment: scanner-sourced runs no longer share the user-watchlist
fundamentals cache. Each Tier-1 survivor gets its own yfinance pull at
fan-out time and the result lands here, keyed by (symbol, fetched_at).

``committee_runs.blended_rank`` carries the 60/40 blend of the L3
committee decision (mapped to a 1-10 score) with the L2 scanner
``composite_pct`` — the spec's final per-candidate ordering.

Both additions are additive and nullable so existing rows stay valid.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "fc8b4e7a9d31"
down_revision: str | Sequence[str] | None = "fb1a4c8d6e92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_fundamentals_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("yfinance_ok", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index(
        "idx_candidate_fundamentals_symbol_fetched",
        "candidate_fundamentals_snapshots",
        ["symbol", sa.text("fetched_at DESC")],
    )

    op.add_column(
        "committee_runs",
        sa.Column("blended_rank", sa.Numeric(5, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("committee_runs", "blended_rank")
    op.drop_index(
        "idx_candidate_fundamentals_symbol_fetched",
        table_name="candidate_fundamentals_snapshots",
    )
    op.drop_table("candidate_fundamentals_snapshots")
