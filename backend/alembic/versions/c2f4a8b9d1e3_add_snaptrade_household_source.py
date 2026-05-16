"""add snaptrade household source

Revision ID: c2f4a8b9d1e3
Revises: b3a9c8d2e7f1
Create Date: 2026-05-16 13:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c2f4a8b9d1e3"
down_revision: str | Sequence[str] | None = "b3a9c8d2e7f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        INSERT INTO source_registry (
            source_id, display_name, priority, enabled, definition, created_at, updated_at
        ) VALUES (
            'snaptrade',
            'SnapTrade',
            55,
            TRUE,
            '{"category":"household_investments","credential_store":"source_credentials","access_mode":"read_only"}'::jsonb,
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
        "snaptrade_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("user_secret_ciphertext", sa.Text(), nullable=False),
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
        sa.UniqueConstraint("user_id", name="uq_snaptrade_users_user_id"),
    )
    op.create_index("idx_snaptrade_users_status", "snaptrade_users", ["status"], unique=False)

    op.create_table(
        "snaptrade_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("authorization_id", sa.Text(), nullable=False),
        sa.Column("brokerage_name", sa.Text(), nullable=True),
        sa.Column("brokerage_slug", sa.Text(), nullable=True),
        sa.Column("connection_name", sa.Text(), nullable=True),
        sa.Column("connection_type", sa.String(length=32), nullable=False, server_default=sa.text("'read'")),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("disabled_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["snaptrade_users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("authorization_id", name="uq_snaptrade_connections_authorization_id"),
    )
    op.create_index(
        "idx_snaptrade_connections_user_id",
        "snaptrade_connections",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "idx_snaptrade_connections_brokerage_slug",
        "snaptrade_connections",
        ["brokerage_slug"],
        unique=False,
    )

    op.create_table(
        "snaptrade_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("authorization_id", sa.Text(), nullable=True),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("portfolio_account_id", sa.Text(), nullable=True),
        sa.Column("household_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("institution_name", sa.Text(), nullable=True),
        sa.Column("account_mask", sa.String(length=64), nullable=True),
        sa.Column("raw_type", sa.Text(), nullable=True),
        sa.Column("portfolio_account_type", sa.String(length=32), nullable=False),
        sa.Column("balance", sa.Numeric(18, 4), nullable=True),
        sa.Column("cash_balance", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["snaptrade_users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["authorization_id"],
            ["snaptrade_connections.authorization_id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["portfolio_account_id"],
            ["portfolio_accounts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["household_account_id"],
            ["household_accounts.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", name="uq_snaptrade_accounts_account_id"),
    )
    op.create_index("idx_snaptrade_accounts_user_id", "snaptrade_accounts", ["user_id"], unique=False)
    op.create_index(
        "idx_snaptrade_accounts_authorization_id",
        "snaptrade_accounts",
        ["authorization_id"],
        unique=False,
    )
    op.create_index(
        "idx_snaptrade_accounts_portfolio_account_id",
        "snaptrade_accounts",
        ["portfolio_account_id"],
        unique=False,
    )
    op.create_index(
        "idx_snaptrade_accounts_household_account_id",
        "snaptrade_accounts",
        ["household_account_id"],
        unique=False,
    )

    op.create_table(
        "snaptrade_positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("position_key", sa.Text(), nullable=False),
        sa.Column("portfolio_position_id", sa.Text(), nullable=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("raw_symbol", sa.Text(), nullable=True),
        sa.Column("security_id", sa.Text(), nullable=True),
        sa.Column("security_kind", sa.String(length=64), nullable=True),
        sa.Column("units", sa.Numeric(24, 8), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("average_purchase_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("market_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("cost_basis", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
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
        sa.ForeignKeyConstraint(["account_id"], ["snaptrade_accounts.account_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["portfolio_position_id"],
            ["portfolio_positions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "position_key", name="uq_snaptrade_positions_account_key"),
    )
    op.create_index(
        "idx_snaptrade_positions_account_id",
        "snaptrade_positions",
        ["account_id"],
        unique=False,
    )
    op.create_index("idx_snaptrade_positions_symbol", "snaptrade_positions", ["symbol"], unique=False)

    op.create_table(
        "snaptrade_activities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("activity_id", sa.Text(), nullable=False),
        sa.Column("activity_type", sa.Text(), nullable=True),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("trade_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settlement_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("units", sa.Numeric(24, 8), nullable=True),
        sa.Column("price", sa.Numeric(18, 6), nullable=True),
        sa.Column("fee", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("external_reference_id", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["account_id"], ["snaptrade_accounts.account_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "activity_id", name="uq_snaptrade_activities_account_activity"),
    )
    op.create_index(
        "idx_snaptrade_activities_account_id",
        "snaptrade_activities",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "idx_snaptrade_activities_trade_date",
        "snaptrade_activities",
        ["trade_date"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_snaptrade_activities_trade_date", table_name="snaptrade_activities")
    op.drop_index("idx_snaptrade_activities_account_id", table_name="snaptrade_activities")
    op.drop_table("snaptrade_activities")

    op.drop_index("idx_snaptrade_positions_symbol", table_name="snaptrade_positions")
    op.drop_index("idx_snaptrade_positions_account_id", table_name="snaptrade_positions")
    op.drop_table("snaptrade_positions")

    op.drop_index("idx_snaptrade_accounts_household_account_id", table_name="snaptrade_accounts")
    op.drop_index("idx_snaptrade_accounts_portfolio_account_id", table_name="snaptrade_accounts")
    op.drop_index("idx_snaptrade_accounts_authorization_id", table_name="snaptrade_accounts")
    op.drop_index("idx_snaptrade_accounts_user_id", table_name="snaptrade_accounts")
    op.drop_table("snaptrade_accounts")

    op.drop_index("idx_snaptrade_connections_brokerage_slug", table_name="snaptrade_connections")
    op.drop_index("idx_snaptrade_connections_user_id", table_name="snaptrade_connections")
    op.drop_table("snaptrade_connections")

    op.drop_index("idx_snaptrade_users_status", table_name="snaptrade_users")
    op.drop_table("snaptrade_users")

    # Keep the source_registry row and any source_credentials rows on downgrade
    # so credentials are never dropped by a schema rollback.
