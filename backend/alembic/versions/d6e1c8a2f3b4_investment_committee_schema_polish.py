"""investment committee schema polish

Revision ID: d6e1c8a2f3b4
Revises: c5a8d3e7b9f1
Create Date: 2026-05-12 00:05:00.000000

Follow-up to ``c5a8d3e7b9f1_add_investment_committee.py`` covering two
issues surfaced during subtask-1 audit (see plan fold-ins #5 and #6
in plans/sunny-puzzling-sprout.md).

1. ``paper_trades.closed_at`` (+ partial open index): the base migration
   shipped ``tracked_until`` but no explicit "open" marker, leaving the
   nightly P/L scan and the open-positions UI without a clear predicate.
   ``closed_at IS NULL`` is now the canonical open predicate; the partial
   index supports the nightly per-symbol scan.

2. ``committee_runs`` status-timestamp CHECK: the base migration accepted
   any timestamp combo for any status. The CHECK enforces the terminal
   states. ``failed`` is not constrained on ``error`` because degenerate
   failures may not produce one.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d6e1c8a2f3b4"
down_revision: str | Sequence[str] | None = "c5a8d3e7b9f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "paper_trades",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_paper_trades_open",
        "paper_trades",
        ["symbol", sa.text("executed_at DESC")],
        postgresql_where=sa.text("closed_at IS NULL"),
    )

    op.create_check_constraint(
        "ck_committee_runs_status_timestamps",
        "committee_runs",
        (
            "(status <> 'complete' OR completed_at IS NOT NULL) "
            "AND (status <> 'approved' "
            "     OR (completed_at IS NOT NULL AND approved_at IS NOT NULL)) "
            "AND (status <> 'aborted' OR aborted_at IS NOT NULL)"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_committee_runs_status_timestamps",
        "committee_runs",
        type_="check",
    )

    op.drop_index("idx_paper_trades_open", table_name="paper_trades")
    op.drop_column("paper_trades", "closed_at")
