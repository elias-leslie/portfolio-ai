"""add portfolio_accounts.is_spouse flag

Revision ID: 7c39a23c677c
Revises: 6b8c1fec4b53
Create Date: 2026-05-09 18:31:00.000000

Adds is_spouse to portfolio_accounts. The IRS wash-sale rule explicitly
covers a spouse's accounts (see Pub 550 / Rev. Rul. 2008-5), so the
TLH/wash-sale checker added in F2 needs a way to recognize spouse-owned
accounts in the same household. Existing rows backfill to false; the
flag is flippable via account edit.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c39a23c677c"
down_revision: str | Sequence[str] | None = "6b8c1fec4b53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "portfolio_accounts",
        sa.Column(
            "is_spouse",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("portfolio_accounts", "is_spouse")
