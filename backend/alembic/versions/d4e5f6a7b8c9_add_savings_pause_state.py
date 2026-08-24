"""make a paused savings target a declared state rather than a zero

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-24 20:10:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Record the pause, why it was taken, and what ends it.

    A ``monthly_savings_target`` of 0 currently reports the household as on
    track: zero trivially keeps up with zero. The pause is stored separately so
    "we are not saving right now, and here is what changes that" can be said out
    loud, with a restart trigger on the income anchor (D17).
    """
    op.execute(
        """
        ALTER TABLE household_profiles
        ADD COLUMN savings_paused_on DATE,
        ADD COLUMN savings_pause_reason TEXT,
        ADD COLUMN savings_restart_income_threshold NUMERIC
        """
    )


def downgrade() -> None:
    """Drop the pause state, leaving only the target amount."""
    op.execute(
        """
        ALTER TABLE household_profiles
        DROP COLUMN savings_paused_on,
        DROP COLUMN savings_pause_reason,
        DROP COLUMN savings_restart_income_threshold
        """
    )
