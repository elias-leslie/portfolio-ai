"""restore missing live db revision

Revision ID: b7c8d9e0f1a2
Revises: 0f6e91c2a8d4
Create Date: 2026-05-16 10:15:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "0f6e91c2a8d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op placeholder for a revision already stamped in the live DB."""


def downgrade() -> None:
    """No-op placeholder for a revision already stamped in the live DB."""
