"""Backfill symbols.company_name from reference cache.

Populates the long-dormant symbols.company_name column (added in migration 058,
always NULL until now) from already-fetched yfinance reference payloads so the
Symbols scanner can show a human-readable company name per row. Cache rows are
heterogeneous (multiple sources/dates per symbol, some payloads carry no name),
so this picks the most recent entry per symbol that actually has a
longName/shortName. Idempotent and offline — no new vendor fetch.

Revision ID: d3f8a1c6b9e2
Revises: c7e4a9b2d8f6
Create Date: 2026-06-05 12:30:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "d3f8a1c6b9e2"
down_revision = "c7e4a9b2d8f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE symbols s
        SET company_name = sub.nm
        FROM (
            SELECT DISTINCT ON (symbol) symbol,
                   COALESCE(payload->>'longName', payload->>'shortName') AS nm
            FROM reference_cache
            WHERE payload IS NOT NULL
              AND COALESCE(payload->>'longName', payload->>'shortName') IS NOT NULL
            ORDER BY symbol, as_of_date DESC
        ) sub
        WHERE sub.symbol = s.symbol
          AND s.company_name IS DISTINCT FROM sub.nm
        """
    )


def downgrade() -> None:
    pass
