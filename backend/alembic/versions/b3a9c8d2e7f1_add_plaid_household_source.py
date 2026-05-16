"""add plaid household source

Revision ID: b3a9c8d2e7f1
Revises: b7c8d9e0f1a2
Create Date: 2026-05-16 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b3a9c8d2e7f1"
down_revision: str | Sequence[str] | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        INSERT INTO source_registry (
            source_id, display_name, priority, enabled, definition, created_at, updated_at
        ) VALUES (
            'plaid',
            'Plaid',
            50,
            TRUE,
            '{"category":"household_finance","credential_store":"source_credentials"}'::jsonb,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT (source_id) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            enabled = TRUE,
            definition = source_registry.definition || EXCLUDED.definition,
            updated_at = CURRENT_TIMESTAMP
        """
    )

    op.create_table(
        "plaid_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", sa.Text(), nullable=False),
        sa.Column("access_token_ciphertext", sa.Text(), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("institution_id", sa.Text(), nullable=True),
        sa.Column("institution_name", sa.Text(), nullable=True),
        sa.Column(
            "available_products",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "billed_products",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "consented_products",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("transactions_cursor", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", name="uq_plaid_items_item_id"),
    )
    op.create_index("idx_plaid_items_status", "plaid_items", ["status"], unique=False)
    op.create_index(
        "idx_plaid_items_institution_id",
        "plaid_items",
        ["institution_id"],
        unique=False,
    )

    op.create_table(
        "plaid_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("household_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("official_name", sa.Text(), nullable=True),
        sa.Column("mask", sa.String(length=64), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=True),
        sa.Column("subtype", sa.String(length=64), nullable=True),
        sa.Column("verification_status", sa.String(length=64), nullable=True),
        sa.Column("current_balance", sa.Numeric(18, 4), nullable=True),
        sa.Column("available_balance", sa.Numeric(18, 4), nullable=True),
        sa.Column("iso_currency_code", sa.String(length=8), nullable=True),
        sa.Column("unofficial_currency_code", sa.String(length=16), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "last_synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["item_id"], ["plaid_items.item_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["household_account_id"],
            ["household_accounts.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", name="uq_plaid_accounts_account_id"),
    )
    op.create_index("idx_plaid_accounts_item_id", "plaid_accounts", ["item_id"], unique=False)
    op.create_index(
        "idx_plaid_accounts_household_account_id",
        "plaid_accounts",
        ["household_account_id"],
        unique=False,
    )

    op.create_table(
        "plaid_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("transaction_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("merchant_name", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("iso_currency_code", sa.String(length=8), nullable=True),
        sa.Column("unofficial_currency_code", sa.String(length=16), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("authorized_date", sa.Date(), nullable=True),
        sa.Column("pending", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("payment_channel", sa.Text(), nullable=True),
        sa.Column(
            "category",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "personal_finance_category",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("removed", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
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
        sa.ForeignKeyConstraint(["item_id"], ["plaid_items.item_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["plaid_accounts.account_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id", name="uq_plaid_transactions_transaction_id"),
    )
    op.create_index(
        "idx_plaid_transactions_account_id",
        "plaid_transactions",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "idx_plaid_transactions_item_id",
        "plaid_transactions",
        ["item_id"],
        unique=False,
    )
    op.create_index(
        "idx_plaid_transactions_transaction_date",
        "plaid_transactions",
        ["transaction_date"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_plaid_transactions_transaction_date", table_name="plaid_transactions")
    op.drop_index("idx_plaid_transactions_item_id", table_name="plaid_transactions")
    op.drop_index("idx_plaid_transactions_account_id", table_name="plaid_transactions")
    op.drop_table("plaid_transactions")

    op.drop_index("idx_plaid_accounts_household_account_id", table_name="plaid_accounts")
    op.drop_index("idx_plaid_accounts_item_id", table_name="plaid_accounts")
    op.drop_table("plaid_accounts")

    op.drop_index("idx_plaid_items_institution_id", table_name="plaid_items")
    op.drop_index("idx_plaid_items_status", table_name="plaid_items")
    op.drop_table("plaid_items")

    # Keep the source_registry row and any source_credentials rows on downgrade
    # so credentials are never dropped by a schema rollback.
