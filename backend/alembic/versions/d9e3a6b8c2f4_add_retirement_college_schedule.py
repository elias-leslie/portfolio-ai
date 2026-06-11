"""Add household retirement college schedule table.

529s are earmarked for college and excluded from retirement buckets;
this schedule carries the planned college spend (real dollars by
calendar year) that the retirement engine funds 529-first.

Revision ID: d9e3a6b8c2f4
Revises: cc06f6a7b8c9
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d9e3a6b8c2f4"
down_revision: str | None = "cc06f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "household_retirement_college_schedule",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("calendar_year", sa.Integer(), nullable=False),
        sa.Column("real_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmation_status", sa.Text(), nullable=False, server_default=sa.text("'confirmed'")),
        sa.Column("provenance", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["source_document_id"], ["household_documents.id"], ondelete="SET NULL", onupdate="CASCADE"),
    )
    op.create_index("idx_household_retirement_college_schedule_updated_at", "household_retirement_college_schedule", ["updated_at"], unique=False)
    op.create_index("idx_household_retirement_college_schedule_source_document_id", "household_retirement_college_schedule", ["source_document_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_household_retirement_college_schedule_source_document_id", table_name="household_retirement_college_schedule")
    op.drop_index("idx_household_retirement_college_schedule_updated_at", table_name="household_retirement_college_schedule")
    op.drop_table("household_retirement_college_schedule")
