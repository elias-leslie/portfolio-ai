"""Mature household transaction provenance and rules.

Revision ID: bc74e8f0a9d1
Revises: a3d7f1c95e24
Create Date: 2026-05-29 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "bc74e8f0a9d1"
down_revision: str | Sequence[str] | None = "a3d7f1c95e24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "household_transaction_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_type", sa.String(length=32), nullable=False, server_default="merchant"),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("normalized_merchant_key", sa.Text(), nullable=True),
        sa.Column("description_pattern", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("essentiality", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="manual"),
        sa.Column("applied_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
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
            ["merchant_id"],
            ["household_merchants.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_household_transaction_rules_merchant_id",
        "household_transaction_rules",
        ["merchant_id"],
    )
    op.create_index(
        "idx_household_transaction_rules_enabled",
        "household_transaction_rules",
        ["enabled"],
    )
    op.create_index(
        "uq_household_transaction_rules_active_merchant",
        "household_transaction_rules",
        ["merchant_id"],
        unique=True,
        postgresql_where=sa.text("enabled IS TRUE AND merchant_id IS NOT NULL"),
    )

    op.add_column(
        "household_transactions",
        sa.Column("source_system", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "household_transactions",
        sa.Column("external_transaction_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "household_transactions",
        sa.Column("original_category", sa.Text(), nullable=True),
    )
    op.add_column(
        "household_transactions",
        sa.Column("categorization_source", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "household_transactions",
        sa.Column("categorization_version", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "household_transactions",
        sa.Column("category_updated_by", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "household_transactions",
        sa.Column("category_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "household_transactions",
        sa.Column("transaction_rule_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "household_transactions",
        sa.Column("import_row_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "household_transactions",
        sa.Column("balance_after", sa.Numeric(18, 4), nullable=True),
    )
    op.add_column(
        "household_transactions",
        sa.Column("pending", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )
    op.add_column(
        "household_transactions",
        sa.Column("removed", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
    )
    op.create_foreign_key(
        "fk_household_transactions_transaction_rule_id",
        "household_transactions",
        "household_transaction_rules",
        ["transaction_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_household_transactions_import_row_id",
        "household_transactions",
        "household_import_rows",
        ["import_row_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_household_transactions_source_system",
        "household_transactions",
        ["source_system"],
    )
    op.create_index(
        "idx_household_transactions_external_transaction_id",
        "household_transactions",
        ["external_transaction_id"],
    )
    op.create_index(
        "idx_household_transactions_transaction_rule_id",
        "household_transactions",
        ["transaction_rule_id"],
    )

    op.execute(
        """
        UPDATE household_transactions
        SET source_system = COALESCE(
                metadata->>'source',
                CASE
                    WHEN metadata ? 'plaid_transaction_id' THEN 'plaid'
                    ELSE NULL
                END
            ),
            external_transaction_id = COALESCE(
                metadata->>'plaid_transaction_id',
                metadata->>'fitid',
                metadata->>'trace_number',
                metadata->>'auth_code'
            ),
            original_category = category,
            categorization_source = CASE
                WHEN metadata->'audit'->>'source' IS NOT NULL THEN metadata->'audit'->>'source'
                WHEN metadata ? 'plaid_transaction_id' THEN 'plaid'
                ELSE COALESCE(metadata->>'source', 'parser')
            END,
            categorization_version = '2026-05-canonical',
            balance_after = CASE
                WHEN COALESCE(metadata->>'balance_after', '') ~ '^-?[0-9,]+(\\.[0-9]+)?$'
                    THEN replace(metadata->>'balance_after', ',', '')::numeric
                ELSE NULL
            END,
            pending = FALSE,
            removed = FALSE
        WHERE source_system IS NULL
           OR original_category IS NULL
           OR categorization_source IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index(
        "idx_household_transactions_transaction_rule_id",
        table_name="household_transactions",
    )
    op.drop_index(
        "idx_household_transactions_external_transaction_id",
        table_name="household_transactions",
    )
    op.drop_index(
        "idx_household_transactions_source_system",
        table_name="household_transactions",
    )
    op.drop_constraint(
        "fk_household_transactions_import_row_id",
        "household_transactions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_household_transactions_transaction_rule_id",
        "household_transactions",
        type_="foreignkey",
    )
    op.drop_column("household_transactions", "removed")
    op.drop_column("household_transactions", "pending")
    op.drop_column("household_transactions", "balance_after")
    op.drop_column("household_transactions", "import_row_id")
    op.drop_column("household_transactions", "transaction_rule_id")
    op.drop_column("household_transactions", "category_updated_at")
    op.drop_column("household_transactions", "category_updated_by")
    op.drop_column("household_transactions", "categorization_version")
    op.drop_column("household_transactions", "categorization_source")
    op.drop_column("household_transactions", "original_category")
    op.drop_column("household_transactions", "external_transaction_id")
    op.drop_column("household_transactions", "source_system")

    op.drop_index(
        "uq_household_transaction_rules_active_merchant",
        table_name="household_transaction_rules",
    )
    op.drop_index(
        "idx_household_transaction_rules_enabled",
        table_name="household_transaction_rules",
    )
    op.drop_index(
        "idx_household_transaction_rules_merchant_id",
        table_name="household_transaction_rules",
    )
    op.drop_table("household_transaction_rules")
