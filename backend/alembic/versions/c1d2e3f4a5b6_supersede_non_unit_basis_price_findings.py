"""compatibility head for databases upgraded before the schema squash

Revision ID: c1d2e3f4a5b6
Revises: e3cf4af42f0a
Create Date: 2026-07-09 19:25:25.883861

Existing installations already recorded this revision before the migration
history was squashed. Keeping the identifier as a no-op head lets those
databases and fresh baseline installs converge on the same Alembic state.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "e3cf4af42f0a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Preserve the pre-squash head as a compatibility marker."""


def downgrade() -> None:
    """Return to the installed squashed baseline marker."""
