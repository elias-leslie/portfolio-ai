"""add committee_runs.source + scanner_rank for fan-out traceability

Revision ID: fb1a4c8d6e92
Revises: fa0e3b7c5d29
Create Date: 2026-05-17 23:30:00.000000

Phase 3 — L3 committee fan-out. Tags every committee run that originates
from the scanner with ``source='scanner_fanout'`` and the per-run
``scanner_rank`` so the unified ``/api/signals/*`` views can show the
provenance and Δrank against the scanner-only ordering. ``source`` is
also a useful filter for cost auditing of the fan-out vs. user-triggered
runs.

Both columns are nullable so existing rows (and ad-hoc user-triggered
runs that don't know their rank) stay valid.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fb1a4c8d6e92"
down_revision: str | Sequence[str] | None = "fa0e3b7c5d29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "committee_runs",
        sa.Column("source", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "committee_runs",
        sa.Column("scanner_rank", sa.Integer(), nullable=True),
    )
    op.create_index(
        "idx_committee_runs_source_started",
        "committee_runs",
        ["source", sa.text("started_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_committee_runs_source_started", table_name="committee_runs")
    op.drop_column("committee_runs", "scanner_rank")
    op.drop_column("committee_runs", "source")
