"""card_rotation_plans + card_rotation_steps (persisted strategy output)

Revision ID: cc04d4e5f6a7
Revises: cc03c3d4e5f6
Create Date: 2026-06-09 09:03:00.000000

The rotation engine can run stateless, but persisting a chosen plan lets the UI
and inbox reference it. A plan is a sequence of quarterly steps.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cc04d4e5f6a7'
down_revision: str | Sequence[str] | None = 'cc03c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the card_rotation_plans and card_rotation_steps tables."""
    op.create_table(
        "card_rotation_plans",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("horizon_quarters", sa.Integer(), nullable=False, server_default=sa.text("8")),
        sa.Column("assumed_monthly_spend", sa.Numeric(12, 2), nullable=False),
        sa.Column("spend_profile", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("projected_total_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("baseline_single_card_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_card_rotation_plans_status", "card_rotation_plans", ["status"], unique=False)

    op.create_table(
        "card_rotation_steps",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("quarter_start", sa.Date(), nullable=True),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("household_credit_card_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_spend", sa.Numeric(12, 2), nullable=True),
        sa.Column("projected_welcome_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("projected_earn_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("rule_warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["plan_id"], ["card_rotation_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["credit_card_products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["household_credit_card_id"], ["household_credit_cards.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_card_rotation_steps_plan_id", "card_rotation_steps", ["plan_id"], unique=False)
    op.create_index("idx_card_rotation_steps_plan_sequence", "card_rotation_steps", ["plan_id", "sequence_index"], unique=False)


def downgrade() -> None:
    """Drop the card_rotation_steps and card_rotation_plans tables."""
    op.drop_index("idx_card_rotation_steps_plan_sequence", table_name="card_rotation_steps")
    op.drop_index("idx_card_rotation_steps_plan_id", table_name="card_rotation_steps")
    op.drop_table("card_rotation_steps")

    op.drop_index("idx_card_rotation_plans_status", table_name="card_rotation_plans")
    op.drop_table("card_rotation_plans")
