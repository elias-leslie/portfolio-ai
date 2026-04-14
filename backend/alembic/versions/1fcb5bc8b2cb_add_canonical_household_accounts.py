"""add canonical household accounts

Revision ID: 1fcb5bc8b2cb
Revises: 6b2a76a1d9f1
Create Date: 2026-04-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1fcb5bc8b2cb"
down_revision: str | Sequence[str] | None = "6b2a76a1d9f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "household_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("primary_identity_key", sa.String(length=512), nullable=True),
        sa.Column("canonical_label", sa.String(length=255), nullable=True),
        sa.Column("asset_group", sa.String(length=32), nullable=False),
        sa.Column("account_type", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("institution_name", sa.String(length=255), nullable=True),
        sa.Column("owner_name", sa.String(length=255), nullable=True),
        sa.Column("account_mask", sa.String(length=64), nullable=True),
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
    )
    op.create_index(
        "uq_household_accounts_primary_identity_key",
        "household_accounts",
        ["primary_identity_key"],
        unique=True,
        postgresql_where=sa.text("primary_identity_key IS NOT NULL"),
    )
    op.create_index(
        "idx_household_accounts_asset_group",
        "household_accounts",
        ["asset_group"],
        unique=False,
    )

    op.create_table(
        "household_account_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("household_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identity_key", sa.String(length=512), nullable=False),
        sa.Column("identity_kind", sa.String(length=64), nullable=False, server_default=sa.text("'composite'")),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
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
        sa.ForeignKeyConstraint(["household_account_id"], ["household_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["household_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_household_account_identities_identity_key",
        "household_account_identities",
        ["identity_key"],
        unique=True,
    )
    op.create_index(
        "idx_household_account_identities_account_id",
        "household_account_identities",
        ["household_account_id"],
        unique=False,
    )

    op.add_column(
        "household_tracked_accounts",
        sa.Column("household_account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_household_tracked_accounts_household_account_id",
        "household_tracked_accounts",
        "household_accounts",
        ["household_account_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "uq_household_tracked_accounts_household_account_id",
        "household_tracked_accounts",
        ["household_account_id"],
        unique=True,
        postgresql_where=sa.text("household_account_id IS NOT NULL"),
    )

    op.add_column(
        "household_evidence_accounts",
        sa.Column("household_account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_household_evidence_accounts_household_account_id",
        "household_evidence_accounts",
        "household_accounts",
        ["household_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_household_evidence_accounts_household_account_id",
        "household_evidence_accounts",
        ["household_account_id"],
        unique=False,
    )

    op.add_column(
        "household_transactions",
        sa.Column("household_account_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_household_transactions_household_account_id",
        "household_transactions",
        "household_accounts",
        ["household_account_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_household_transactions_household_account_id",
        "household_transactions",
        ["household_account_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "idx_household_transactions_household_account_id",
        table_name="household_transactions",
    )
    op.drop_constraint(
        "fk_household_transactions_household_account_id",
        "household_transactions",
        type_="foreignkey",
    )
    op.drop_column("household_transactions", "household_account_id")

    op.drop_index(
        "idx_household_evidence_accounts_household_account_id",
        table_name="household_evidence_accounts",
    )
    op.drop_constraint(
        "fk_household_evidence_accounts_household_account_id",
        "household_evidence_accounts",
        type_="foreignkey",
    )
    op.drop_column("household_evidence_accounts", "household_account_id")

    op.drop_index(
        "uq_household_tracked_accounts_household_account_id",
        table_name="household_tracked_accounts",
    )
    op.drop_constraint(
        "fk_household_tracked_accounts_household_account_id",
        "household_tracked_accounts",
        type_="foreignkey",
    )
    op.drop_column("household_tracked_accounts", "household_account_id")

    op.drop_index(
        "idx_household_account_identities_account_id",
        table_name="household_account_identities",
    )
    op.drop_index(
        "uq_household_account_identities_identity_key",
        table_name="household_account_identities",
    )
    op.drop_table("household_account_identities")

    op.drop_index(
        "idx_household_accounts_asset_group",
        table_name="household_accounts",
    )
    op.drop_index(
        "uq_household_accounts_primary_identity_key",
        table_name="household_accounts",
    )
    op.drop_table("household_accounts")

