"""hold the per-fund sinking overrides the derivation cannot know

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-24 20:40:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """One row per fund, holding only what the ledger cannot derive.

    The monthly amount is computed from trailing spend every time the dashboard
    is built, so nothing here caches it. What is stored is the household's
    judgement: a declared amount with the day it was declared, and whether the
    largest purchase in the window was a one-time event that should not set the
    monthly rate (D18).
    """
    op.execute(
        """
        CREATE TABLE household_sinking_funds (
            id UUID PRIMARY KEY,
            fund_key TEXT NOT NULL UNIQUE,
            monthly_override NUMERIC,
            override_set_on DATE,
            override_note TEXT,
            drop_largest BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    """Drop the per-fund judgements, leaving only the derivation."""
    op.execute("DROP TABLE household_sinking_funds")
