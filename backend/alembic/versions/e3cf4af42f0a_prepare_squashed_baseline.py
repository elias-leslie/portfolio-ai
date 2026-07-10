"""install the squashed Portfolio AI schema baseline

Revision ID: e3cf4af42f0a
Revises:
Create Date: 2026-07-09 19:25:25.883861

"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3cf4af42f0a"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Install the complete schema for a fresh database."""
    baseline_path = Path(__file__).resolve().parents[1] / "baseline.sql"
    driver_connection = op.get_bind().connection.driver_connection
    with driver_connection.cursor() as cursor:
        # Extensions are infrastructure prerequisites owned by PostgreSQL in
        # existing installs and by the database owner in fresh CI installs.
        # CREATE IF NOT EXISTS is safe in both cases and keeps Alembic the
        # authority for constructing an empty Portfolio database.
        cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cursor.execute(baseline_path.read_text(encoding="utf-8"), prepare=False)


def downgrade() -> None:
    """Refuse destructive removal of the entire baseline schema."""
    raise RuntimeError("The squashed baseline cannot be downgraded safely")
