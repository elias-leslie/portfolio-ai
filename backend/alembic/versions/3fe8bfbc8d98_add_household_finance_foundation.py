import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3fe8bfbc8d98'
down_revision: str | None = 'eadedfee7cef'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add persistent household planning and document intake tables."""
    op.create_table(
        "household_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("household_name", sa.Text(), nullable=False, server_default=sa.text("'Household'")),
        sa.Column("monthly_net_income_target", sa.Numeric(12, 2), nullable=True),
        sa.Column("monthly_essential_target", sa.Numeric(12, 2), nullable=True),
        sa.Column("monthly_discretionary_target", sa.Numeric(12, 2), nullable=True),
        sa.Column("monthly_savings_target", sa.Numeric(12, 2), nullable=True),
        sa.Column("target_retirement_age", sa.Integer(), nullable=True),
        sa.Column("target_retirement_spend", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_household_profiles_updated_at", "household_profiles", ["updated_at"], unique=False)

    op.create_table(
        "household_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("document_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'staged'")),
        sa.Column("account_label", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("classification_confidence", sa.Float(), nullable=True),
        sa.Column("statement_start", sa.Date(), nullable=True),
        sa.Column("statement_end", sa.Date(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("idx_household_documents_uploaded_at", "household_documents", ["uploaded_at"], unique=False)
    op.create_index("idx_household_documents_status", "household_documents", ["status"], unique=False)
    op.create_index("idx_household_documents_source_type", "household_documents", ["source_type"], unique=False)


def downgrade() -> None:
    """Remove household planning and document intake tables."""
    op.drop_index("idx_household_documents_source_type", table_name="household_documents")
    op.drop_index("idx_household_documents_status", table_name="household_documents")
    op.drop_index("idx_household_documents_uploaded_at", table_name="household_documents")
    op.drop_table("household_documents")

    op.drop_index("idx_household_profiles_updated_at", table_name="household_profiles")
    op.drop_table("household_profiles")
