"""let a household appeal a row that the spend filters dropped

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-23 10:05:00.000000

``_household_spend_filters.py`` drops any row whose text matches a literal
string -- "zelle to", "atm withdrawal", "payroll", "online transfer" -- or whose
category is one of transfers/income/cash/debt payments. The list is a reasonable
default and a bad verdict: a Zelle payment to a tutor is real spend, an ATM
withdrawal that became groceries is real spend, and both vanish from every total
with no way to say otherwise. 138 of 996 ledger rows are dropped this way.

This adds the one fact the filter cannot derive: what the household says about a
specific row. ``spend_override`` is 'include' when a person has said a dropped
row is real spend, 'exclude' when they have said a counted row is not, and NULL
-- the overwhelming majority -- when nobody has said anything and the rules
decide as before.

Deliberately a column rather than a metadata key: the spend predicate is built
in SQL and evaluated in several queries, so the override has to be visible to
SQL or it would apply on some surfaces and not others, which is the class of bug
this phase exists to remove. Nothing is backfilled -- an override means a person
spoke, and inventing one would defeat the point.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Record the household's verdict on a row, where they have given one."""
    op.add_column(
        "household_transactions",
        sa.Column("spend_override", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "household_transactions",
        sa.Column("spend_override_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "household_transactions",
        sa.Column(
            "spend_override_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "household_transactions_spend_override_check",
        "household_transactions",
        "spend_override IS NULL OR spend_override IN ('include', 'exclude')",
    )
    # Partial index: the column is NULL for nearly every row, and the only
    # queries that touch it are looking for the handful that are not.
    op.create_index(
        "ix_household_transactions_spend_override",
        "household_transactions",
        ["spend_override"],
        postgresql_where=sa.text("spend_override IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_household_transactions_spend_override",
        table_name="household_transactions",
    )
    op.drop_constraint(
        "household_transactions_spend_override_check",
        "household_transactions",
        type_="check",
    )
    op.drop_column("household_transactions", "spend_override_at")
    op.drop_column("household_transactions", "spend_override_reason")
    op.drop_column("household_transactions", "spend_override")
