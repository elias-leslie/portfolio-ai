"""Make price_cache a canonical current quote table.

Revision ID: e6b4c2a9d8f1
Revises: d5a8b6c4e9f2
Create Date: 2026-06-04 09:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e6b4c2a9d8f1"
down_revision: str | Sequence[str] | None = "d5a8b6c4e9f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM price_cache older
        USING price_cache newer
        WHERE UPPER(older.symbol) = UPPER(newer.symbol)
          AND (
              older.cached_at < newer.cached_at
              OR (older.cached_at = newer.cached_at AND older.ctid < newer.ctid)
          )
        """
    )
    op.execute("DROP INDEX IF EXISTS idx_price_cache_symbol")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_price_cache_symbol_current "
        "ON price_cache (UPPER(symbol))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_price_cache_symbol_current")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_price_cache_symbol "
        "ON price_cache (symbol, cached_at)"
    )
