"""clear current mirrors for inactive source accounts

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-07-12 20:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d9e0f1a2b3c4"
down_revision: str | Sequence[str] | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove stale current snapshots without deleting provider history."""
    op.execute(
        """
        WITH inactive_portfolio_accounts AS (
            SELECT DISTINCT source_account.portfolio_account_id
            FROM snaptrade_accounts AS source_account
            WHERE source_account.is_active = FALSE
              AND source_account.portfolio_account_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM snaptrade_accounts AS active_account
                  JOIN snaptrade_connections AS active_connection
                    ON active_connection.authorization_id = active_account.authorization_id
                  WHERE active_account.portfolio_account_id = source_account.portfolio_account_id
                    AND active_account.is_active = TRUE
                    AND active_connection.is_active = TRUE
                    AND active_connection.disabled = FALSE
              )
        )
        DELETE FROM portfolio_positions AS position
        USING inactive_portfolio_accounts AS inactive
        WHERE position.account_id = inactive.portfolio_account_id
          AND (position.id LIKE 'snaptrade:%%' OR position.strategy_id IS NULL)
        """
    )
    op.execute(
        """
        WITH inactive_portfolio_accounts AS (
            SELECT DISTINCT source_account.portfolio_account_id
            FROM snaptrade_accounts AS source_account
            WHERE source_account.is_active = FALSE
              AND source_account.portfolio_account_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM snaptrade_accounts AS active_account
                  JOIN snaptrade_connections AS active_connection
                    ON active_connection.authorization_id = active_account.authorization_id
                  WHERE active_account.portfolio_account_id = source_account.portfolio_account_id
                    AND active_account.is_active = TRUE
                    AND active_connection.is_active = TRUE
                    AND active_connection.disabled = FALSE
              )
        )
        UPDATE portfolio_accounts AS account
        SET cash_balance = 0,
            updated_at = CURRENT_TIMESTAMP
        FROM inactive_portfolio_accounts AS inactive
        WHERE account.id = inactive.portfolio_account_id
        """
    )
    op.execute(
        """
        DELETE FROM household_evidence_accounts AS evidence
        USING household_documents AS document, plaid_items AS item
        WHERE document.id = evidence.document_id
          AND document.source_type = 'plaid'
          AND document.document_type = 'api_sync'
          AND document.metadata->>'plaid_item_id' = item.item_id
          AND item.status <> 'active'
        """
    )


def downgrade() -> None:
    """Current snapshots cannot be reconstructed during downgrade."""
