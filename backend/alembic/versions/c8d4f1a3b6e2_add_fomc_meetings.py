"""add fomc_meetings

Revision ID: c8d4f1a3b6e2
Revises: 8a4e92c1d3f0
Create Date: 2026-05-09 21:00:00.000000

F4 introduces a forward-catalyst calendar covering earnings,
ex-dividend, and FOMC events. Earnings + ex-dividend dates are
already cached in ``reference_cache`` (symbol-keyed); FOMC meetings
are macro events with no symbol so they get their own tiny table.

The Hatchet ``portfolio-catalyst-prewarm`` task refreshes this table
quarterly from the Federal Reserve calendar JSON, and the
:class:`CatalystCalendarService` reads it on every ``GET
/api/catalysts/upcoming`` call to merge macro events into the symbol
calendar.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c8d4f1a3b6e2"
down_revision: str | Sequence[str] | None = "8a4e92c1d3f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "fomc_meetings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("meeting_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("meeting_date", name="uq_fomc_meetings_meeting_date"),
        sa.CheckConstraint(
            "meeting_type IN ('regular','press_conference','minutes')",
            name="ck_fomc_meetings_meeting_type",
        ),
    )
    op.create_index(
        "ix_fomc_meetings_meeting_date",
        "fomc_meetings",
        ["meeting_date"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_fomc_meetings_meeting_date", table_name="fomc_meetings")
    op.drop_table("fomc_meetings")
