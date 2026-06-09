"""household_credit_cards (user-owned / candidate cards)

Revision ID: cc02b2c3d4e5
Revises: cc01a1b2c3d4
Create Date: 2026-06-09 09:01:00.000000

Cards the household owns or is considering. A partial unique index enforces the
"one card at a time" rule: at most one row may have ``is_primary_active = TRUE``.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cc02b2c3d4e5'
down_revision: str | Sequence[str] | None = 'cc01a1b2c3d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the household_credit_cards table."""
    op.create_table(
        "household_credit_cards",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("household_account_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'candidate'")),
        sa.Column("is_primary_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("opened_date", sa.Date(), nullable=True),
        sa.Column("closed_date", sa.Date(), nullable=True),
        sa.Column("annual_fee_due_date", sa.Date(), nullable=True),
        # Spend accumulated toward the welcome minimum spend, in dollars (same
        # units as credit_card_products.welcome_min_spend).
        sa.Column("welcome_progress_amount", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("welcome_deadline", sa.Date(), nullable=True),
        sa.Column("welcome_status", sa.Text(), nullable=False, server_default=sa.text("'not_started'")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["product_id"], ["credit_card_products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["household_account_id"], ["household_accounts.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_household_credit_cards_product_id", "household_credit_cards", ["product_id"], unique=False)
    op.create_index("idx_household_credit_cards_status", "household_credit_cards", ["status"], unique=False)
    op.create_index("idx_household_credit_cards_household_account_id", "household_credit_cards", ["household_account_id"], unique=False)
    # The "one card at a time" pointer: at most one primary-active card.
    op.create_index(
        "uq_household_credit_cards_primary_active",
        "household_credit_cards",
        ["is_primary_active"],
        unique=True,
        postgresql_where=sa.text("is_primary_active"),
    )


def downgrade() -> None:
    """Drop the household_credit_cards table."""
    op.drop_index("uq_household_credit_cards_primary_active", table_name="household_credit_cards")
    op.drop_index("idx_household_credit_cards_household_account_id", table_name="household_credit_cards")
    op.drop_index("idx_household_credit_cards_status", table_name="household_credit_cards")
    op.drop_index("idx_household_credit_cards_product_id", table_name="household_credit_cards")
    op.drop_table("household_credit_cards")
