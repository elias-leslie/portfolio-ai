"""add household evidence accounts

Revision ID: e528b11bec24
Revises: 281842054872
Create Date: 2026-04-09 13:25:37.970829

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e528b11bec24'
down_revision: str | Sequence[str] | None = '281842054872'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "household_evidence_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("asset_group", sa.String(length=32), nullable=False),
        sa.Column("account_type", sa.String(length=64), nullable=False),
        sa.Column("institution_name", sa.String(length=255), nullable=True),
        sa.Column("account_name", sa.String(length=255), nullable=True),
        sa.Column("account_mask", sa.String(length=32), nullable=True),
        sa.Column("owner_name", sa.String(length=255), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("balance", sa.Numeric(18, 4), nullable=True),
        sa.Column("holdings_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("cash_balance", sa.Numeric(18, 4), nullable=True),
        sa.Column("as_of_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["household_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_household_evidence_accounts_document_id",
        "household_evidence_accounts",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "idx_household_evidence_accounts_asset_group",
        "household_evidence_accounts",
        ["asset_group"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "idx_household_evidence_accounts_asset_group",
        table_name="household_evidence_accounts",
    )
    op.drop_index(
        "idx_household_evidence_accounts_document_id",
        table_name="household_evidence_accounts",
    )
    op.drop_table("household_evidence_accounts")
