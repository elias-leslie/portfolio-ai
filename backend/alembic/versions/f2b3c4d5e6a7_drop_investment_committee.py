"""drop investment committee

Revision ID: f2b3c4d5e6a7
Revises: e0f1a2b3c4d5
Create Date: 2026-08-18 16:30:00.000000

Remove the multi-agent investment-committee subsystem. The fan-out workflow
that scheduled runs was already deleted in ``f4a7c9e2d6b8``; nothing has been
able to start a run since, and the last one finished 2026-05-19. This drops
the eight ``committee_*`` tables plus ``paper_trades``, which only the
committee decision path ever wrote to.

Every row was dumped to JSON before this ran; see the archive noted in the
decommission commit. ``paper_trade_transactions`` is a different table on a
different code path and is deliberately left in place.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f2b3c4d5e6a7"
down_revision: str | Sequence[str] | None = "e0f1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Children before parents: every table below carries an FK into
    # committee_runs (or, for ingestion health, into the approvals table).
    op.execute("DROP TABLE IF EXISTS paper_trades")
    op.execute("DROP TABLE IF EXISTS committee_widgets")
    op.execute("DROP TABLE IF EXISTS committee_source_snapshots")
    op.execute("DROP TABLE IF EXISTS committee_inputs")
    op.execute("DROP TABLE IF EXISTS committee_evidence")
    op.execute("DROP TABLE IF EXISTS committee_events")
    op.execute("DROP TABLE IF EXISTS committee_runs")
    op.execute("DROP TABLE IF EXISTS committee_source_ingestion_health")
    op.execute("DROP TABLE IF EXISTS committee_data_source_approvals")


def downgrade() -> None:
    """Refuse to recreate a subsystem whose code no longer exists."""
    raise RuntimeError(
        "The investment committee was decommissioned; its tables cannot be "
        "restored by downgrade. Restore from the JSON archive taken before "
        "revision f2b3c4d5e6a7 if the history is needed."
    )
