"""add tlh_scan_results snapshot table

Revision ID: e055f9ddb756
Revises: 7c39a23c677c
Create Date: 2026-05-09 18:50:00.000000

F2 introduces a daily Hatchet workflow (`portfolio-tlh-scan`,
cron `0 13 * * 1-5`) that materializes TLH candidates so CLI reads
are O(1). The workflow truncates the day's rows up-front and reinserts
inside one transaction, so re-runs are safely idempotent.

Indexes are tuned for the agentic read patterns:
- `(scan_date DESC)` for "what was new today"
- `(scan_date, account_id)` for the per-account drill-down
- `(scan_date, symbol)` for the symbol-level pivot
- partial-unique `(scan_date, account_id, symbol)` to enforce the
  one-row-per-day-per-position contract used by the workflow's
  upsert-by-day strategy.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e055f9ddb756"
down_revision: str | Sequence[str] | None = "7c39a23c677c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tlh_scan_results",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("scan_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("unrealized_loss", sa.Numeric(18, 4), nullable=False),
        sa.Column("unrealized_loss_pct", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "blocked_by_wash_sale",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("wash_sale_reason", sa.Text(), nullable=True),
        sa.Column("replacement_symbol", sa.String(length=32), nullable=True),
        sa.Column("holding_period_days", sa.Integer(), nullable=True),
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
        "ix_tlh_scan_results_scan_date",
        "tlh_scan_results",
        [sa.text("scan_date DESC")],
    )
    op.create_index(
        "ix_tlh_scan_results_scan_date_account",
        "tlh_scan_results",
        ["scan_date", "account_id"],
    )
    op.create_index(
        "ix_tlh_scan_results_scan_date_symbol",
        "tlh_scan_results",
        ["scan_date", "symbol"],
    )
    op.create_index(
        "uq_tlh_scan_results_day_position",
        "tlh_scan_results",
        ["scan_date", "account_id", "symbol"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_tlh_scan_results_day_position", table_name="tlh_scan_results")
    op.drop_index("ix_tlh_scan_results_scan_date_symbol", table_name="tlh_scan_results")
    op.drop_index("ix_tlh_scan_results_scan_date_account", table_name="tlh_scan_results")
    op.drop_index("ix_tlh_scan_results_scan_date", table_name="tlh_scan_results")
    op.drop_table("tlh_scan_results")
