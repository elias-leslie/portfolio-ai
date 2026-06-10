"""add floor-and-upside withdrawal plan

Revision ID: b3d9e1c4a7f2
Revises: cc05e5f6a7b8
Create Date: 2026-06-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b3d9e1c4a7f2"
down_revision: str | Sequence[str] | None = "cc05e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("household_profiles", sa.Column("withdrawal_strategy", sa.Text(), nullable=True))
    op.add_column("household_profiles", sa.Column("withdrawal_initial_rate", sa.Numeric(6, 5), nullable=True))
    op.add_column("household_profiles", sa.Column("withdrawal_decline_mode", sa.Text(), nullable=True))
    op.add_column("household_profiles", sa.Column("discretionary_decline_rate", sa.Numeric(6, 5), nullable=True))
    op.add_column("household_profiles", sa.Column("phase_slow_go_age", sa.Integer(), nullable=True))
    op.add_column("household_profiles", sa.Column("phase_no_go_age", sa.Integer(), nullable=True))
    op.add_column("household_profiles", sa.Column("phase_go_go_pct", sa.Numeric(5, 4), nullable=True))
    op.add_column("household_profiles", sa.Column("phase_slow_go_pct", sa.Numeric(5, 4), nullable=True))
    op.add_column("household_profiles", sa.Column("phase_no_go_pct", sa.Numeric(5, 4), nullable=True))
    op.add_column("household_profiles", sa.Column("bridge_mode", sa.Text(), nullable=True))
    op.add_column("household_profiles", sa.Column("bridge_manual_amount", sa.Numeric(12, 2), nullable=True))
    op.add_column("household_profiles", sa.Column("bridge_real_return", sa.Numeric(6, 5), nullable=True))
    op.add_column("household_profiles", sa.Column("retirement_essential_floor_override", sa.Numeric(12, 2), nullable=True))
    op.add_column("household_profiles", sa.Column("retirement_discretionary_override", sa.Numeric(12, 2), nullable=True))

    op.create_table(
        "household_retirement_healthcare_schedule",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
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
    op.create_index("idx_household_retirement_healthcare_schedule_updated_at", "household_retirement_healthcare_schedule", ["updated_at"], unique=False)
    op.create_index("idx_household_retirement_healthcare_schedule_source_document_id", "household_retirement_healthcare_schedule", ["source_document_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_household_retirement_healthcare_schedule_source_document_id", table_name="household_retirement_healthcare_schedule")
    op.drop_index("idx_household_retirement_healthcare_schedule_updated_at", table_name="household_retirement_healthcare_schedule")
    op.drop_table("household_retirement_healthcare_schedule")

    op.drop_column("household_profiles", "retirement_discretionary_override")
    op.drop_column("household_profiles", "retirement_essential_floor_override")
    op.drop_column("household_profiles", "bridge_real_return")
    op.drop_column("household_profiles", "bridge_manual_amount")
    op.drop_column("household_profiles", "bridge_mode")
    op.drop_column("household_profiles", "phase_no_go_pct")
    op.drop_column("household_profiles", "phase_slow_go_pct")
    op.drop_column("household_profiles", "phase_go_go_pct")
    op.drop_column("household_profiles", "phase_no_go_age")
    op.drop_column("household_profiles", "phase_slow_go_age")
    op.drop_column("household_profiles", "discretionary_decline_rate")
    op.drop_column("household_profiles", "withdrawal_decline_mode")
    op.drop_column("household_profiles", "withdrawal_initial_rate")
    op.drop_column("household_profiles", "withdrawal_strategy")
