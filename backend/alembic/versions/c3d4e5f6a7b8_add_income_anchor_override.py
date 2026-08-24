"""record a declared income anchor beside the measured one

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-24 19:40:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Store the override, the day it was declared, and why.

    The date is not decoration: an anchor declared before a job started is a
    fact, and the same anchor still standing six months later is a guess. The
    measured median stays computed either way so both can be shown together.
    """
    op.execute(
        """
        ALTER TABLE household_profiles
        ADD COLUMN income_anchor_override NUMERIC,
        ADD COLUMN income_anchor_override_set_on DATE,
        ADD COLUMN income_anchor_override_note TEXT
        """
    )


def downgrade() -> None:
    """Drop the declared anchor, leaving only the measured median."""
    op.execute(
        """
        ALTER TABLE household_profiles
        DROP COLUMN income_anchor_override,
        DROP COLUMN income_anchor_override_set_on,
        DROP COLUMN income_anchor_override_note
        """
    )
