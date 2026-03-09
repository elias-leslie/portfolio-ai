"""add household transaction ledger and merchants

Revision ID: c1b476112bf4
Revises: 9e7a0b64a51d
Create Date: 2026-03-09 10:57:50.092284

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c1b476112bf4"
down_revision: str | Sequence[str] | None = "9e7a0b64a51d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "household_merchants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("normalized_key", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("primary_category", sa.Text(), nullable=True),
        sa.Column("essentiality", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_key", name="uq_household_merchants_normalized_key"),
    )
    op.create_index(
        "idx_household_merchants_primary_category",
        "household_merchants",
        ["primary_category"],
    )

    op.create_table(
        "household_transactions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("merchant_id", sa.UUID(), nullable=True),
        sa.Column("row_hash", sa.String(length=128), nullable=False),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("posted_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("raw_merchant", sa.Text(), nullable=True),
        sa.Column("account_label", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="USD"),
        sa.Column("flow_type", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("essentiality", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["household_documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["merchant_id"],
            ["household_merchants.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("row_hash", name="uq_household_transactions_row_hash"),
    )
    op.create_index(
        "idx_household_transactions_document_id",
        "household_transactions",
        ["document_id"],
    )
    op.create_index(
        "idx_household_transactions_merchant_id",
        "household_transactions",
        ["merchant_id"],
    )
    op.create_index(
        "idx_household_transactions_transaction_date",
        "household_transactions",
        ["transaction_date"],
    )
    op.create_index(
        "idx_household_transactions_flow_type",
        "household_transactions",
        ["flow_type"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_household_transactions_flow_type", table_name="household_transactions")
    op.drop_index("idx_household_transactions_transaction_date", table_name="household_transactions")
    op.drop_index("idx_household_transactions_merchant_id", table_name="household_transactions")
    op.drop_index("idx_household_transactions_document_id", table_name="household_transactions")
    op.drop_table("household_transactions")
    op.drop_index("idx_household_merchants_primary_category", table_name="household_merchants")
    op.drop_table("household_merchants")
