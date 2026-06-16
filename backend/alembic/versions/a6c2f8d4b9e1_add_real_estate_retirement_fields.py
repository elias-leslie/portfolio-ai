"""add real estate retirement fields

Revision ID: a6c2f8d4b9e1
Revises: f6b9c1d2e3a4, 281842054872
Create Date: 2026-06-16 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6c2f8d4b9e1"
down_revision: str | Sequence[str] | None = ("f6b9c1d2e3a4", "281842054872")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.household_profiles') IS NOT NULL THEN
                UPDATE household_profiles SET withdrawal_strategy = 'guardrails';
            END IF;
            IF to_regclass('public.retirement_scenarios') IS NOT NULL THEN
                UPDATE retirement_scenarios
                SET
                    inputs = jsonb_set(inputs, '{withdrawal,strategy}', '"guardrails"', true),
                    results = jsonb_set(results, '{inputs,withdrawal,strategy}', '"guardrails"', true)
                WHERE inputs #>> '{withdrawal,strategy}' IS NOT NULL
                   OR results #>> '{inputs,withdrawal,strategy}' IS NOT NULL;
            END IF;
        END $$;
        """
    )
    op.add_column(
        "household_housing_costs",
        sa.Column("property_value", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "household_housing_costs",
        sa.Column("ownership_percent", sa.Numeric(6, 3), nullable=True),
    )
    op.add_column(
        "household_housing_costs",
        sa.Column("value_as_of", sa.Date(), nullable=True),
    )
    op.add_column(
        "household_housing_costs",
        sa.Column(
            "retirement_treatment",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'track_only'"),
        ),
    )
    op.add_column(
        "household_housing_costs",
        sa.Column("annual_retirement_income", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "household_housing_costs",
        sa.Column("liquidity_year", sa.Integer(), nullable=True),
    )
    op.add_column(
        "household_housing_costs",
        sa.Column("liquidity_amount", sa.Numeric(14, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("household_housing_costs", "liquidity_amount")
    op.drop_column("household_housing_costs", "liquidity_year")
    op.drop_column("household_housing_costs", "annual_retirement_income")
    op.drop_column("household_housing_costs", "retirement_treatment")
    op.drop_column("household_housing_costs", "value_as_of")
    op.drop_column("household_housing_costs", "ownership_percent")
    op.drop_column("household_housing_costs", "property_value")
