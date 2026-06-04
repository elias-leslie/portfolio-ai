"""add price_cache quote provenance (price_session, quote_time)

Revision ID: b2d9f4a7c1e3
Revises: f4a7c9e2d6b8
Create Date: 2026-06-04 17:10:00.000000

Adds quote provenance to the canonical current-quote table so freshness can be
judged honestly. ``quote_time`` is the vendor's quote timestamp (e.g. CBOE
last_trade_time / Yahoo regularMarketTime) rather than ``cached_at`` (the time we
wrote the row). ``price_session`` records which session the price came from
(regular / delayed / previous_close / ...) so a carried-forward prior close can
never masquerade as a live quote. Both columns are nullable; existing rows and
sources that do not supply them are unaffected.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b2d9f4a7c1e3"
down_revision: str | Sequence[str] | None = "f4a7c9e2d6b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE price_cache ADD COLUMN IF NOT EXISTS price_session text")
    op.execute("ALTER TABLE price_cache ADD COLUMN IF NOT EXISTS quote_time timestamptz")


def downgrade() -> None:
    op.execute("ALTER TABLE price_cache DROP COLUMN IF EXISTS quote_time")
    op.execute("ALTER TABLE price_cache DROP COLUMN IF EXISTS price_session")
