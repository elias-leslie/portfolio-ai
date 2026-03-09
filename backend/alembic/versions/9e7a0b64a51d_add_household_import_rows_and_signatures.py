"""add household import rows and signatures

Revision ID: 9e7a0b64a51d
Revises: f47c8ec06a52
Create Date: 2026-03-09 09:28:24.440686

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '9e7a0b64a51d'
down_revision: str | Sequence[str] | None = 'f47c8ec06a52'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "household_document_signatures",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signature_key", sa.String(length=255), nullable=False),
        sa.Column("signature_type", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=False),
        sa.Column("merchant", sa.String(length=255), nullable=True),
        sa.Column("account_hint", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("sample_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("match_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["sample_document_id"], ["household_documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("signature_key", name="uq_household_document_signatures_signature_key"),
    )
    op.create_index(
        "idx_household_document_signatures_type",
        "household_document_signatures",
        ["signature_type"],
        unique=False,
    )
    op.create_index(
        "idx_household_document_signatures_sample_document_id",
        "household_document_signatures",
        ["sample_document_id"],
        unique=False,
    )

    op.create_table(
        "household_import_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_type", sa.String(length=64), nullable=False),
        sa.Column("row_hash", sa.String(length=255), nullable=False),
        sa.Column("external_row_id", sa.String(length=255), nullable=True),
        sa.Column("row_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merchant", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("row_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["household_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("row_hash", name="uq_household_import_rows_row_hash"),
    )
    op.create_index(
        "idx_household_import_rows_document_id",
        "household_import_rows",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "idx_household_import_rows_dataset_type",
        "household_import_rows",
        ["dataset_type"],
        unique=False,
    )
    op.create_index(
        "idx_household_import_rows_external_row_id",
        "household_import_rows",
        ["external_row_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_household_import_rows_external_row_id", table_name="household_import_rows")
    op.drop_index("idx_household_import_rows_dataset_type", table_name="household_import_rows")
    op.drop_index("idx_household_import_rows_document_id", table_name="household_import_rows")
    op.drop_table("household_import_rows")

    op.drop_index(
        "idx_household_document_signatures_sample_document_id",
        table_name="household_document_signatures",
    )
    op.drop_index(
        "idx_household_document_signatures_type",
        table_name="household_document_signatures",
    )
    op.drop_table("household_document_signatures")
