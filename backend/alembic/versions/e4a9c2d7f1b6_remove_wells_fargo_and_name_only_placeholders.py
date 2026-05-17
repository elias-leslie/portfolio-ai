"""Remove Wells Fargo household data and name-only placeholders.

Revision ID: e4a9c2d7f1b6
Revises: d8f1c3a7b9e2
Create Date: 2026-05-17 15:31:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "e4a9c2d7f1b6"
down_revision = "d8f1c3a7b9e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TEMP TABLE tmp_wells_fargo_documents
        ON COMMIT DROP AS
        SELECT id
        FROM household_documents
        WHERE lower(COALESCE(filename, '')) LIKE '%wells%'
           OR lower(COALESCE(account_label, '')) LIKE '%wells%'
           OR id IN (
                SELECT document_id
                FROM household_evidence_accounts
                WHERE lower(COALESCE(institution_name, '')) LIKE '%wells fargo%'
                   OR lower(COALESCE(account_name, '')) LIKE '%wells fargo%'
           )
        """
    )
    op.execute(
        """
        CREATE TEMP TABLE tmp_wells_fargo_accounts
        ON COMMIT DROP AS
        SELECT id
        FROM household_accounts
        WHERE lower(COALESCE(institution_name, '')) LIKE '%wells fargo%'
           OR lower(COALESCE(canonical_label, '')) LIKE '%wells fargo%'
           OR id IN (
                SELECT household_account_id
                FROM household_transactions
                WHERE household_account_id IS NOT NULL
                  AND document_id IN (SELECT id FROM tmp_wells_fargo_documents)
           )
        """
    )
    op.execute(
        """
        DELETE FROM household_transactions
        WHERE document_id IN (SELECT id FROM tmp_wells_fargo_documents)
           OR household_account_id IN (SELECT id FROM tmp_wells_fargo_accounts)
           OR lower(COALESCE(account_label, '')) LIKE '%wells%'
        """
    )
    op.execute(
        """
        DELETE FROM household_evidence_accounts
        WHERE document_id IN (SELECT id FROM tmp_wells_fargo_documents)
           OR household_account_id IN (SELECT id FROM tmp_wells_fargo_accounts)
           OR lower(COALESCE(institution_name, '')) LIKE '%wells fargo%'
           OR lower(COALESCE(account_name, '')) LIKE '%wells fargo%'
        """
    )
    op.execute(
        """
        DELETE FROM household_account_preferences
        WHERE household_account_id IN (SELECT id FROM tmp_wells_fargo_accounts)
        """
    )
    op.execute(
        """
        DELETE FROM household_account_identities
        WHERE household_account_id IN (SELECT id FROM tmp_wells_fargo_accounts)
        """
    )
    op.execute(
        """
        DELETE FROM household_accounts
        WHERE id IN (SELECT id FROM tmp_wells_fargo_accounts)
        """
    )
    op.execute(
        """
        UPDATE household_evidence_accounts ea
        SET household_account_id = preserved.id
        FROM household_accounts preserved
        WHERE ea.metadata->>'preserved_household_account_id' = preserved.id::text
        """
    )
    op.execute(
        """
        UPDATE household_evidence_accounts ea
        SET household_account_id = matched.id
        FROM household_accounts matched
        WHERE ea.metadata->>'match_key' = matched.primary_identity_key
          AND ea.account_mask IS NULL
          AND matched.account_mask IS NULL
        """
    )
    op.execute(
        """
        CREATE TEMP TABLE tmp_name_only_household_placeholders
        ON COMMIT DROP AS
        SELECT ha.id
        FROM household_accounts ha
        LEFT JOIN household_evidence_accounts ea ON ea.household_account_id = ha.id
        LEFT JOIN household_transactions tx ON tx.household_account_id = ha.id
        LEFT JOIN portfolio_accounts portfolio ON portfolio.household_account_id = ha.id
        LEFT JOIN plaid_accounts plaid ON plaid.household_account_id = ha.id
        LEFT JOIN snaptrade_accounts snaptrade ON snaptrade.household_account_id = ha.id
        WHERE ha.account_mask IS NULL
          AND ha.primary_identity_key LIKE 'institution-name%'
        GROUP BY ha.id
        HAVING COUNT(DISTINCT ea.id) = 0
           AND COUNT(DISTINCT tx.id) = 0
           AND COUNT(DISTINCT portfolio.id) = 0
           AND COUNT(DISTINCT plaid.id) = 0
           AND COUNT(DISTINCT snaptrade.id) = 0
        """
    )
    op.execute(
        """
        DELETE FROM household_account_preferences
        WHERE household_account_id IN (
            SELECT id FROM tmp_name_only_household_placeholders
        )
        """
    )
    op.execute(
        """
        DELETE FROM household_account_identities
        WHERE household_account_id IN (
            SELECT id FROM tmp_name_only_household_placeholders
        )
        """
    )
    op.execute(
        """
        DELETE FROM household_accounts
        WHERE id IN (
            SELECT id FROM tmp_name_only_household_placeholders
        )
        """
    )
    op.execute(
        """
        CREATE TEMP TABLE tmp_orphan_household_accounts
        ON COMMIT DROP AS
        SELECT ha.id
        FROM household_accounts ha
        LEFT JOIN household_evidence_accounts ea ON ea.household_account_id = ha.id
        LEFT JOIN household_account_preferences pref ON pref.household_account_id = ha.id
        LEFT JOIN household_transactions tx ON tx.household_account_id = ha.id
        LEFT JOIN portfolio_accounts portfolio ON portfolio.household_account_id = ha.id
        LEFT JOIN plaid_accounts plaid ON plaid.household_account_id = ha.id
        LEFT JOIN snaptrade_accounts snaptrade ON snaptrade.household_account_id = ha.id
        GROUP BY ha.id
        HAVING COUNT(DISTINCT ea.id) = 0
           AND COUNT(DISTINCT pref.id) = 0
           AND COUNT(DISTINCT tx.id) = 0
           AND COUNT(DISTINCT portfolio.id) = 0
           AND COUNT(DISTINCT plaid.id) = 0
           AND COUNT(DISTINCT snaptrade.id) = 0
        """
    )
    op.execute(
        """
        DELETE FROM household_account_identities
        WHERE household_account_id IN (
            SELECT id FROM tmp_orphan_household_accounts
        )
        """
    )
    op.execute(
        """
        DELETE FROM household_accounts
        WHERE id IN (
            SELECT id FROM tmp_orphan_household_accounts
        )
        """
    )


def downgrade() -> None:
    pass
