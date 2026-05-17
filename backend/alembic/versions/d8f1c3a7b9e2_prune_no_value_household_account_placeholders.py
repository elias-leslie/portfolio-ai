"""Prune no-value household account placeholders.

Revision ID: d8f1c3a7b9e2
Revises: c2f4a8b9d1e3
Create Date: 2026-05-17 12:09:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "d8f1c3a7b9e2"
down_revision = "c2f4a8b9d1e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TEMP TABLE tmp_no_value_household_account_placeholders
        ON COMMIT DROP AS
        SELECT ha.id
        FROM household_accounts ha
        JOIN household_evidence_accounts ea ON ea.household_account_id = ha.id
        LEFT JOIN household_account_preferences pref ON pref.household_account_id = ha.id
        LEFT JOIN household_tracked_accounts tracked ON tracked.household_account_id = ha.id
        LEFT JOIN household_transactions tx ON tx.household_account_id = ha.id
        LEFT JOIN portfolio_accounts portfolio ON portfolio.household_account_id = ha.id
        LEFT JOIN plaid_accounts plaid ON plaid.household_account_id = ha.id
        LEFT JOIN snaptrade_accounts snaptrade ON snaptrade.household_account_id = ha.id
        GROUP BY ha.id
        HAVING COUNT(DISTINCT pref.id) = 0
           AND COUNT(DISTINCT tracked.id) = 0
           AND COUNT(DISTINCT tx.id) = 0
           AND COUNT(DISTINCT portfolio.id) = 0
           AND COUNT(DISTINCT plaid.id) = 0
           AND COUNT(DISTINCT snaptrade.id) = 0
           AND BOOL_AND(
                ea.balance IS NULL
                AND ea.holdings_value IS NULL
                AND ea.cash_balance IS NULL
           )
        """
    )
    op.execute(
        """
        UPDATE household_evidence_accounts
        SET household_account_id = NULL
        WHERE household_account_id IN (
            SELECT id FROM tmp_no_value_household_account_placeholders
        )
        """
    )
    op.execute(
        """
        DELETE FROM household_account_identities
        WHERE household_account_id IN (
            SELECT id FROM tmp_no_value_household_account_placeholders
        )
        """
    )
    op.execute(
        """
        DELETE FROM household_accounts
        WHERE id IN (
            SELECT id FROM tmp_no_value_household_account_placeholders
        )
        """
    )


def downgrade() -> None:
    pass
