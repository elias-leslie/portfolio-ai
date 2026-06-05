"""Mark user-confirmed closed household accounts.

Revision ID: c7e4a9b2d8f6
Revises: b2d9f4a7c1e3
Create Date: 2026-06-05 11:05:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "c7e4a9b2d8f6"
down_revision = "b2d9f4a7c1e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TEMP TABLE tmp_user_confirmed_closed_household_accounts
        ON COMMIT DROP AS
        SELECT id
        FROM household_accounts
        WHERE lower(COALESCE(institution_name, '')) LIKE '%wells fargo%'
           OR lower(COALESCE(canonical_label, '')) LIKE '%wells fargo%'
           OR lower(COALESCE(institution_name, '')) LIKE '%cb&t cust ira%'
           OR lower(COALESCE(canonical_label, '')) LIKE '%cb&t cust ira%'
        """
    )
    op.execute(
        """
        UPDATE household_accounts
        SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                'account_status', 'closed',
                'status_confirmed_by', 'user',
                'status_confirmed_at', '2026-06-05',
                'status_note',
                'User confirmed this account is closed; do not request current balance or cash-flow action.'
            ),
            updated_at = now()
        WHERE id IN (
            SELECT id FROM tmp_user_confirmed_closed_household_accounts
        )
        """
    )
    op.execute(
        """
        UPDATE household_evidence_accounts
        SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                'account_status', 'closed',
                'status_confirmed_by', 'user',
                'status_confirmed_at', '2026-06-05'
            )
        WHERE household_account_id IN (
            SELECT id FROM tmp_user_confirmed_closed_household_accounts
        )
        """
    )


def downgrade() -> None:
    pass
