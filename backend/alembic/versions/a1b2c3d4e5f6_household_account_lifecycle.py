"""track household account lifecycle and registry merges

Revision ID: a1b2c3d4e5f6
Revises: f2b3c4d5e6a7
Create Date: 2026-08-22 10:40:00.000000

Rolling spend windows currently treat every account in the registry as if it
were still reporting. Several are not: two feeds stopped in February 2026 when
the underlying accounts were closed, so a 12-month window blends a live card
against checking uploads that ended six months ago and reports income with no
matching spend.

This adds the two facts a window needs in order to state its own coverage
honestly -- ``feed_status`` (is this account still reporting?) and
``coverage_through`` (through what date?) -- plus the columns that let one
registry row be retired into another (``merged_into_account_id``,
``archived_at``, ``archive_reason``) so duplicate identities and transferred
accounts stop being counted twice.

Archival is deliberately reversible: nothing is deleted, and a row retired by
mistake is restored by clearing ``archived_at``. The backfill below derives
status from observed transaction recency only -- which accounts belong to whom,
and which merge into which, are runtime decisions made through the registry
service, never literals committed to this repository.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f2b3c4d5e6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# An account whose newest transaction is older than this is no longer a feed a
# rolling window may quietly include. Two months is wide enough to survive a
# late statement drop and narrow enough to catch a feed that stopped.
_DORMANT_AFTER_DAYS = 60


def upgrade() -> None:
    """Give every account an honest feed status and a coverage horizon."""
    op.add_column(
        "household_accounts",
        sa.Column(
            "feed_status",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "household_accounts",
        sa.Column("coverage_through", sa.Date(), nullable=True),
    )
    op.add_column(
        "household_accounts",
        sa.Column("merged_into_account_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "household_accounts",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "household_accounts",
        sa.Column("archive_reason", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        "household_accounts_merged_into_fkey",
        "household_accounts",
        "household_accounts",
        ["merged_into_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_household_accounts_feed_status",
        "household_accounts",
        ["feed_status"],
    )
    op.create_index(
        "ix_household_accounts_archived_at",
        "household_accounts",
        ["archived_at"],
    )

    # Derive coverage from what each account has actually reported. Accounts with
    # no transactions at all keep coverage_through NULL and status 'unknown' --
    # net-worth-only holdings are legitimately in this state and must not be
    # mislabelled as dead feeds.
    op.execute(
        """
        UPDATE household_accounts AS a
        SET coverage_through = observed.last_txn_date
        FROM (
            SELECT household_account_id,
                   MAX(transaction_date)::date AS last_txn_date
            FROM household_transactions
            WHERE household_account_id IS NOT NULL
              AND NOT removed
            GROUP BY household_account_id
        ) AS observed
        WHERE a.id = observed.household_account_id
        """
    )
    op.execute(
        f"""
        UPDATE household_accounts
        SET feed_status = CASE
            WHEN coverage_through IS NULL THEN 'unknown'
            WHEN coverage_through >= (CURRENT_DATE - INTERVAL '{_DORMANT_AFTER_DAYS} days')
                THEN 'live'
            ELSE 'dormant'
        END
        """
    )


def downgrade() -> None:
    op.drop_index("ix_household_accounts_archived_at", table_name="household_accounts")
    op.drop_index("ix_household_accounts_feed_status", table_name="household_accounts")
    op.drop_constraint(
        "household_accounts_merged_into_fkey",
        "household_accounts",
        type_="foreignkey",
    )
    op.drop_column("household_accounts", "archive_reason")
    op.drop_column("household_accounts", "archived_at")
    op.drop_column("household_accounts", "merged_into_account_id")
    op.drop_column("household_accounts", "coverage_through")
    op.drop_column("household_accounts", "feed_status")
