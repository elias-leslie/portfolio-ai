"""register application tables for freshness metadata

Revision ID: b7c8d9e0f1a2
Revises: f825742b0002
Create Date: 2026-07-12 18:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "f825742b0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DESCRIPTION = "Registered automatically by Alembic for freshness metadata"


def upgrade() -> None:
    """Populate metadata rows missing from fresh squashed-baseline databases."""
    op.execute(
        f"""
        INSERT INTO table_registry (table_name, table_type, description, row_count)
        SELECT
            tables.table_name,
            'application',
            '{_DESCRIPTION}',
            0
        FROM information_schema.tables AS tables
        WHERE tables.table_schema = 'public'
          AND tables.table_type = 'BASE TABLE'
          AND tables.table_name NOT IN (
              'alembic_version',
              'schema_migrations',
              'table_registry'
          )
        ON CONFLICT (table_name) DO NOTHING
        """
    )


def downgrade() -> None:
    """Remove only metadata rows created by this migration."""
    op.execute(
        f"DELETE FROM table_registry WHERE description = '{_DESCRIPTION}'"
    )
