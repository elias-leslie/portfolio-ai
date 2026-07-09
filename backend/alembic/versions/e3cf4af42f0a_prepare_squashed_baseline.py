"""prepare squashed baseline

Revision ID: e3cf4af42f0a
Revises: c1d2e3f4a5b6
Create Date: 2026-07-09 19:25:25.883861

"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "e3cf4af42f0a"
down_revision: str | Sequence[str] | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
