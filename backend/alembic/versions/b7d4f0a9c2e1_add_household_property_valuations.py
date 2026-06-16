"""add household property valuations

Revision ID: b7d4f0a9c2e1
Revises: a6c2f8d4b9e1
Create Date: 2026-06-16 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7d4f0a9c2e1"
down_revision: str | Sequence[str] | None = "a6c2f8d4b9e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "household_housing_costs",
        sa.Column("property_address", sa.Text(), nullable=True),
    )
    op.add_column(
        "household_housing_costs",
        sa.Column("valuation_source", sa.Text(), nullable=True),
    )
    op.add_column(
        "household_housing_costs",
        sa.Column("valuation_confidence", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "household_housing_costs",
        sa.Column("valuation_range_low", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "household_housing_costs",
        sa.Column("valuation_range_high", sa.Numeric(14, 2), nullable=True),
    )

    op.create_table(
        "household_property_valuations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "housing_cost_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("household_housing_costs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_label", sa.Text(), nullable=False),
        sa.Column("estimate_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("range_low", sa.Numeric(14, 2), nullable=True),
        sa.Column("range_high", sa.Numeric(14, 2), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("methodology", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.UniqueConstraint(
            "housing_cost_id",
            "source",
            "as_of",
            name="uq_household_property_valuations_snapshot",
        ),
    )
    op.create_index(
        "ix_household_property_valuations_housing_fetched",
        "household_property_valuations",
        ["housing_cost_id", "fetched_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_household_property_valuations_housing_fetched",
        table_name="household_property_valuations",
    )
    op.drop_table("household_property_valuations")
    op.drop_column("household_housing_costs", "valuation_range_high")
    op.drop_column("household_housing_costs", "valuation_range_low")
    op.drop_column("household_housing_costs", "valuation_confidence")
    op.drop_column("household_housing_costs", "valuation_source")
    op.drop_column("household_housing_costs", "property_address")
