"""link portfolio accounts to household accounts

Revision ID: 52c8f3b4a1e9
Revises: 1fcb5bc8b2cb
Create Date: 2026-04-14 00:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "52c8f3b4a1e9"
down_revision: str | Sequence[str] | None = "1fcb5bc8b2cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "portfolio_accounts",
        sa.Column("household_account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_portfolio_accounts_household_account_id",
        "portfolio_accounts",
        "household_accounts",
        ["household_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_portfolio_accounts_household_account_id",
        "portfolio_accounts",
        ["household_account_id"],
        unique=True,
        postgresql_where=sa.text("household_account_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_portfolio_accounts_household_account_id",
        table_name="portfolio_accounts",
    )
    op.drop_constraint(
        "fk_portfolio_accounts_household_account_id",
        "portfolio_accounts",
        type_="foreignkey",
    )
    op.drop_column("portfolio_accounts", "household_account_id")
