"""add ppi market event type

Revision ID: 0f6e91c2a8d4
Revises: f3c5d8a1b9e7
Create Date: 2026-05-13 13:55:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0f6e91c2a8d4"
down_revision: str | Sequence[str] | None = "f3c5d8a1b9e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add Producer Price Index releases to the macro event enum."""
    op.execute("ALTER TYPE market_event_type ADD VALUE IF NOT EXISTS 'ppi_release'")


def downgrade() -> None:
    """PostgreSQL enum values are intentionally left in place."""
