"""Add SnapTrade orders mirror table.

Revision ID: d5a8b6c4e9f2
Revises: c1a2b3d4e5f6
Create Date: 2026-06-03 19:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5a8b6c4e9f2"
down_revision: str | Sequence[str] | None = "c1a2b3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "snaptrade_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("brokerage_order_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=True),
        sa.Column("symbol", sa.Text(), nullable=True),
        sa.Column("raw_symbol", sa.Text(), nullable=True),
        sa.Column("filled_quantity", sa.Numeric(24, 8), nullable=True),
        sa.Column("execution_price", sa.Numeric(18, 6), nullable=True),
        sa.Column("order_type", sa.Text(), nullable=True),
        sa.Column("time_in_force", sa.Text(), nullable=True),
        sa.Column("time_placed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_executed", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["snaptrade_accounts.account_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "brokerage_order_id",
            name="uq_snaptrade_orders_account_brokerage_order",
        ),
    )
    op.create_index(
        "idx_snaptrade_orders_account_id",
        "snaptrade_orders",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "idx_snaptrade_orders_symbol",
        "snaptrade_orders",
        ["symbol"],
        unique=False,
    )
    op.create_index(
        "idx_snaptrade_orders_status",
        "snaptrade_orders",
        ["status"],
        unique=False,
    )
    op.create_index(
        "idx_snaptrade_orders_time_executed",
        "snaptrade_orders",
        [sa.text("time_executed DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_snaptrade_orders_time_executed", table_name="snaptrade_orders")
    op.drop_index("idx_snaptrade_orders_status", table_name="snaptrade_orders")
    op.drop_index("idx_snaptrade_orders_symbol", table_name="snaptrade_orders")
    op.drop_index("idx_snaptrade_orders_account_id", table_name="snaptrade_orders")
    op.drop_table("snaptrade_orders")
