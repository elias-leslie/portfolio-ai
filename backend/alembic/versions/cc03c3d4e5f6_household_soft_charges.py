"""household_soft_charges (phone-entered provisional ledger)

Revision ID: cc03c3d4e5f6
Revises: cc02b2c3d4e5
Create Date: 2026-06-09 09:02:00.000000

Provisional charges entered by phone (amount + description, optional receipt)
so pending spend counts toward budget immediately. Each soft charge writes a
mirror row into household_transactions; the SoftChargeReconciler matches it to
the real Plaid transaction and voids the mirror to avoid double counting.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cc03c3d4e5f6'
down_revision: str | Sequence[str] | None = 'cc02b2c3d4e5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the household_soft_charges table."""
    op.create_table(
        "household_soft_charges",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("household_account_id", sa.UUID(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("merchant", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("essentiality", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.Date(), nullable=False),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        # Id of the matched hard household_transactions row (Plaid-sourced).
        sa.Column("matched_plaid_transaction_id", sa.UUID(), nullable=True),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("match_confidence", sa.Float(), nullable=True),
        sa.Column("match_method", sa.Text(), nullable=True),
        # Id of the synthetic household_transactions mirror row this soft charge created.
        sa.Column("ledger_transaction_id", sa.UUID(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["household_account_id"], ["household_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_document_id"], ["household_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["matched_plaid_transaction_id"], ["household_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ledger_transaction_id"], ["household_transactions.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_household_soft_charges_status", "household_soft_charges", ["status"], unique=False)
    op.create_index("idx_household_soft_charges_account_occurred", "household_soft_charges", ["household_account_id", "occurred_at"], unique=False)
    op.create_index("idx_household_soft_charges_matched_plaid", "household_soft_charges", ["matched_plaid_transaction_id"], unique=False)


def downgrade() -> None:
    """Drop the household_soft_charges table."""
    op.drop_index("idx_household_soft_charges_matched_plaid", table_name="household_soft_charges")
    op.drop_index("idx_household_soft_charges_account_occurred", table_name="household_soft_charges")
    op.drop_index("idx_household_soft_charges_status", table_name="household_soft_charges")
    op.drop_table("household_soft_charges")
