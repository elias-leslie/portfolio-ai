"""add portfolio_transactions and portfolio_tax_lots

Revision ID: 6b8c1fec4b53
Revises: d7f3a9c2b8e1
Create Date: 2026-05-09 18:30:00.000000

Foundation for the F1 ledger described in
plans/concurrent-dancing-hennessy.md. The ledger powers TLH/wash-sale
checks, tax-aware rebalancing, and broker-import idempotency.

Tables:
- portfolio_transactions: append-only buy/sell/dividend/split rows.
  source='legacy_aggregate' rows preserve historical aggregate writes
  from PortfolioManager. external_id is partial-unique per account so
  broker imports are safely retryable.
- portfolio_tax_lots: open-lot rows. remaining_shares is decremented
  by FIFO consumption when sells are recorded. acquisition_txn_id is
  nullable so legacy backfills can leave it empty without breaking FK.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "6b8c1fec4b53"
down_revision: str | Sequence[str] | None = "d7f3a9c2b8e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "portfolio_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("transaction_type", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("settlement_date", sa.Date(), nullable=True),
        sa.Column("shares", sa.Numeric(18, 6), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "fees",
            sa.Numeric(18, 4),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("realized_gain", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "source",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
        sa.Column("external_id", sa.String(length=128), nullable=True),
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
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["portfolio_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_portfolio_transactions_account_symbol_date",
        "portfolio_transactions",
        ["account_id", "symbol", "trade_date"],
    )
    op.create_index(
        "idx_portfolio_transactions_trade_date",
        "portfolio_transactions",
        ["trade_date"],
    )
    op.create_index(
        "uq_portfolio_transactions_account_external_id",
        "portfolio_transactions",
        ["account_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "portfolio_tax_lots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("acquired_date", sa.Date(), nullable=False),
        sa.Column("original_shares", sa.Numeric(18, 6), nullable=False),
        sa.Column("remaining_shares", sa.Numeric(18, 6), nullable=False),
        sa.Column("cost_per_share", sa.Numeric(18, 6), nullable=False),
        sa.Column("cost_basis_total", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "acquisition_txn_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("disposed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["portfolio_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["acquisition_txn_id"],
            ["portfolio_transactions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_portfolio_tax_lots_open",
        "portfolio_tax_lots",
        ["account_id", "symbol", "remaining_shares"],
    )
    op.create_index(
        "idx_portfolio_tax_lots_acquired_date",
        "portfolio_tax_lots",
        ["acquired_date"],
    )
    op.create_index(
        "idx_portfolio_tax_lots_fifo",
        "portfolio_tax_lots",
        ["account_id", "symbol", "acquired_date"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_portfolio_tax_lots_fifo", table_name="portfolio_tax_lots")
    op.drop_index(
        "idx_portfolio_tax_lots_acquired_date", table_name="portfolio_tax_lots"
    )
    op.drop_index("idx_portfolio_tax_lots_open", table_name="portfolio_tax_lots")
    op.drop_table("portfolio_tax_lots")

    op.drop_index(
        "uq_portfolio_transactions_account_external_id",
        table_name="portfolio_transactions",
    )
    op.drop_index(
        "idx_portfolio_transactions_trade_date",
        table_name="portfolio_transactions",
    )
    op.drop_index(
        "idx_portfolio_transactions_account_symbol_date",
        table_name="portfolio_transactions",
    )
    op.drop_table("portfolio_transactions")
