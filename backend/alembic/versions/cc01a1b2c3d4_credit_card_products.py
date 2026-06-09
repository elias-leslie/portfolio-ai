"""credit_card_products reference catalog

Revision ID: cc01a1b2c3d4
Revises: be759a462b74
Create Date: 2026-06-09 09:00:00.000000

First of four migrations for the Credit Card Management feature. Reference
catalog of card products (seeded + extended via offer intake). Reward terms
change often, so every row carries ``last_verified_at`` and seed values are
"verify at apply time".
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cc01a1b2c3d4'
down_revision: str | Sequence[str] | None = 'be759a462b74'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the credit_card_products reference catalog."""
    op.create_table(
        "credit_card_products",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("issuer", sa.Text(), nullable=False),
        sa.Column("network", sa.Text(), nullable=True),
        sa.Column("product_name", sa.Text(), nullable=False),
        sa.Column("card_kind", sa.Text(), nullable=False, server_default=sa.text("'personal'")),
        sa.Column("annual_fee", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("reward_multipliers", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("point_program", sa.Text(), nullable=True),
        sa.Column("est_point_value_cents", sa.Numeric(6, 3), nullable=True),
        sa.Column("welcome_bonus_points", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("welcome_bonus_cash", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("welcome_min_spend", sa.Numeric(12, 2), nullable=True),
        sa.Column("welcome_window_days", sa.Integer(), nullable=True),
        sa.Column("transfer_partners", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("credits", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("issuer_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'seed'")),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.ForeignKeyConstraint(["source_document_id"], ["household_documents.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_credit_card_products_issuer", "credit_card_products", ["issuer"], unique=False)
    op.create_index("idx_credit_card_products_point_program", "credit_card_products", ["point_program"], unique=False)


def downgrade() -> None:
    """Drop the credit_card_products reference catalog."""
    op.drop_index("idx_credit_card_products_point_program", table_name="credit_card_products")
    op.drop_index("idx_credit_card_products_issuer", table_name="credit_card_products")
    op.drop_table("credit_card_products")
