"""add household document review and question queue

Revision ID: f47c8ec06a52
Revises: 3fe8bfbc8d98
Create Date: 2026-03-08 23:54:10.019761

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f47c8ec06a52'
down_revision: str | Sequence[str] | None = '3fe8bfbc8d98'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("household_documents", sa.Column("review_status", sa.Text(), nullable=True))
    op.add_column("household_documents", sa.Column("review_summary", sa.Text(), nullable=True))
    op.add_column("household_documents", sa.Column("review_confidence", sa.Float(), nullable=True))
    op.create_index(
        "idx_household_documents_review_status",
        "household_documents",
        ["review_status"],
        unique=False,
    )

    op.create_table(
        "household_document_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("household_documents.id", ondelete="CASCADE", onupdate="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column(
            "structured_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(
        "idx_household_document_reviews_document_id",
        "household_document_reviews",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "idx_household_document_reviews_created_at",
        "household_document_reviews",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "household_inferred_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("field_name", sa.Text(), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'inferred'")),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("household_documents.id", ondelete="SET NULL", onupdate="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_household_inferred_values_field_name", "household_inferred_values", ["field_name"], unique=False)
    op.create_index(
        "idx_household_inferred_values_source_document_id",
        "household_inferred_values",
        ["source_document_id"],
        unique=False,
    )
    op.create_index("idx_household_inferred_values_updated_at", "household_inferred_values", ["updated_at"], unique=False)

    op.create_table(
        "household_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("field_name", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("priority", sa.Text(), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("household_documents.id", ondelete="SET NULL", onupdate="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_household_questions_status", "household_questions", ["status"], unique=False)
    op.create_index("idx_household_questions_field_name", "household_questions", ["field_name"], unique=False)
    op.create_index(
        "idx_household_questions_source_document_id",
        "household_questions",
        ["source_document_id"],
        unique=False,
    )
    op.create_index("idx_household_questions_created_at", "household_questions", ["created_at"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_household_questions_created_at", table_name="household_questions")
    op.drop_index("idx_household_questions_source_document_id", table_name="household_questions")
    op.drop_index("idx_household_questions_field_name", table_name="household_questions")
    op.drop_index("idx_household_questions_status", table_name="household_questions")
    op.drop_table("household_questions")

    op.drop_index("idx_household_inferred_values_updated_at", table_name="household_inferred_values")
    op.drop_index("idx_household_inferred_values_source_document_id", table_name="household_inferred_values")
    op.drop_index("idx_household_inferred_values_field_name", table_name="household_inferred_values")
    op.drop_table("household_inferred_values")

    op.drop_index("idx_household_document_reviews_created_at", table_name="household_document_reviews")
    op.drop_index("idx_household_document_reviews_document_id", table_name="household_document_reviews")
    op.drop_table("household_document_reviews")

    op.drop_index("idx_household_documents_review_status", table_name="household_documents")
    op.drop_column("household_documents", "review_confidence")
    op.drop_column("household_documents", "review_summary")
    op.drop_column("household_documents", "review_status")
