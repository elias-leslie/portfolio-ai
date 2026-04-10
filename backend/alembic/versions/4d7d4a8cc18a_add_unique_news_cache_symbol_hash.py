"""add unique news cache symbol hash

Revision ID: 4d7d4a8cc18a
Revises: b917dfebe69d
Create Date: 2026-04-10 17:09:13.415985

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4d7d4a8cc18a'
down_revision: str | Sequence[str] | None = 'b917dfebe69d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        DELETE FROM news_cache older
        USING news_cache newer
        WHERE older.symbol = newer.symbol
          AND older.content_hash = newer.content_hash
          AND (
              older.fetched_at < newer.fetched_at
              OR (older.fetched_at = newer.fetched_at AND older.id < newer.id)
          )
        """
    )
    op.execute("DROP INDEX IF EXISTS news_cache_symbol_hash")
    op.execute(
        """
        CREATE UNIQUE INDEX news_cache_symbol_hash
        ON news_cache (symbol, content_hash)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS news_cache_symbol_hash")
    op.execute(
        """
        CREATE INDEX news_cache_symbol_hash
        ON news_cache (symbol, content_hash)
        """
    )
