"""track authoritative source account lifecycle

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-07-12 19:15:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: str | Sequence[str] | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Keep source history while separating current provider snapshots."""
    for table_name in ("plaid_accounts", "snaptrade_connections", "snaptrade_accounts"):
        op.add_column(
            table_name,
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )
        op.add_column(
            table_name,
            sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        )

    op.execute(
        """
        UPDATE plaid_accounts AS pa
        SET is_active = FALSE,
            removed_at = CURRENT_TIMESTAMP
        FROM plaid_items AS pi
        WHERE pi.item_id = pa.item_id
          AND pi.status <> 'active'
        """
    )
    op.execute(
        """
        UPDATE snaptrade_connections
        SET is_active = FALSE,
            removed_at = COALESCE(disabled_date, CURRENT_TIMESTAMP)
        WHERE disabled = TRUE
        """
    )
    op.execute(
        """
        UPDATE snaptrade_accounts AS sa
        SET is_active = FALSE,
            removed_at = COALESCE(sc.disabled_date, CURRENT_TIMESTAMP)
        FROM snaptrade_connections AS sc
        WHERE sc.authorization_id = sa.authorization_id
          AND (sc.disabled = TRUE OR sc.is_active = FALSE)
        """
    )

    op.create_index(
        "idx_plaid_accounts_active_item",
        "plaid_accounts",
        ["item_id"],
        unique=False,
        postgresql_where=sa.text("is_active = TRUE"),
    )
    op.create_index(
        "idx_snaptrade_connections_active_user",
        "snaptrade_connections",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("is_active = TRUE"),
    )
    op.create_index(
        "idx_snaptrade_accounts_active_authorization",
        "snaptrade_accounts",
        ["authorization_id"],
        unique=False,
        postgresql_where=sa.text("is_active = TRUE"),
    )


def downgrade() -> None:
    """Remove source lifecycle state."""
    op.drop_index(
        "idx_snaptrade_accounts_active_authorization",
        table_name="snaptrade_accounts",
    )
    op.drop_index(
        "idx_snaptrade_connections_active_user",
        table_name="snaptrade_connections",
    )
    op.drop_index("idx_plaid_accounts_active_item", table_name="plaid_accounts")
    for table_name in ("snaptrade_accounts", "snaptrade_connections", "plaid_accounts"):
        op.drop_column(table_name, "removed_at")
        op.drop_column(table_name, "is_active")
