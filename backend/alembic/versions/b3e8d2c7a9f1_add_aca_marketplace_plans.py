"""ACA marketplace landscape plans (CMS QHP landscape PUF).

Age-rated marketplace premiums by county and metal tier feed the
retirement ACA estimator: benchmark Silver / lowest Bronze premiums at
the household's modeled ages, real published rates only — never
invented numbers. Rows come from the CMS "QHP Landscape Individual
Medical" public use file, refreshed annually after open enrollment
publishes the next plan year.

Revision ID: b3e8d2c7a9f1
Revises: f2b8d3e9a1c5
Create Date: 2026-06-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b3e8d2c7a9f1"
down_revision: str | None = "f2b8d3e9a1c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "aca_marketplace_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_year", sa.Integer(), nullable=False),
        sa.Column("state_code", sa.Text(), nullable=False),
        sa.Column("fips_county_code", sa.Text(), nullable=False),
        sa.Column("county_name", sa.Text(), nullable=True),
        sa.Column("metal_level", sa.Text(), nullable=False),
        sa.Column("issuer_name", sa.Text(), nullable=True),
        sa.Column("plan_id", sa.Text(), nullable=False),
        sa.Column("plan_marketing_name", sa.Text(), nullable=True),
        sa.Column("standardized_plan_option", sa.Text(), nullable=True),
        sa.Column("plan_type", sa.Text(), nullable=True),
        sa.Column("rating_area", sa.Text(), nullable=True),
        sa.Column("ehb_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("premium_child_age_0_14", sa.Numeric(10, 2), nullable=True),
        sa.Column("premium_child_age_18", sa.Numeric(10, 2), nullable=True),
        sa.Column("premium_age_21", sa.Numeric(10, 2), nullable=True),
        sa.Column("premium_age_27", sa.Numeric(10, 2), nullable=True),
        sa.Column("premium_age_30", sa.Numeric(10, 2), nullable=True),
        sa.Column("premium_age_40", sa.Numeric(10, 2), nullable=True),
        sa.Column("premium_age_50", sa.Numeric(10, 2), nullable=True),
        sa.Column("premium_age_60", sa.Numeric(10, 2), nullable=True),
        sa.Column("medical_deductible_individual", sa.Numeric(10, 2), nullable=True),
        sa.Column("medical_moop_individual", sa.Numeric(10, 2), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("plan_year", "fips_county_code", "plan_id", name="uq_aca_marketplace_plans_year_county_plan"),
    )
    op.create_index(
        "idx_aca_marketplace_plans_lookup",
        "aca_marketplace_plans",
        ["plan_year", "state_code", "fips_county_code", "metal_level"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_aca_marketplace_plans_lookup", table_name="aca_marketplace_plans")
    op.drop_table("aca_marketplace_plans")
