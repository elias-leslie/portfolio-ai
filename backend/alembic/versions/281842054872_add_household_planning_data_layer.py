"""add household planning data layer

Revision ID: 281842054872
Revises: 5ce02b41a5a8
Create Date: 2026-03-11 17:55:00.453464

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = '281842054872'
down_revision: Union[str, Sequence[str], None] = '5ce02b41a5a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("household_profiles", sa.Column("adult_count", sa.Integer(), nullable=True))
    op.add_column("household_profiles", sa.Column("dependent_count", sa.Integer(), nullable=True))
    op.add_column("household_profiles", sa.Column("filing_status", sa.Text(), nullable=True))
    op.add_column("household_profiles", sa.Column("state_of_residence", sa.Text(), nullable=True))
    op.add_column("household_profiles", sa.Column("effective_tax_rate", sa.Numeric(6, 2), nullable=True))
    op.add_column("household_profiles", sa.Column("marginal_federal_tax_rate", sa.Numeric(6, 2), nullable=True))
    op.add_column("household_profiles", sa.Column("marginal_state_tax_rate", sa.Numeric(6, 2), nullable=True))
    op.add_column("household_profiles", sa.Column("emergency_fund_target_months", sa.Numeric(6, 2), nullable=True))
    op.add_column("household_profiles", sa.Column("emergency_fund_target_amount", sa.Numeric(12, 2), nullable=True))

    op.create_table(
        "household_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("relationship", sa.Text(), nullable=True),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("is_dependent", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("lives_in_household", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmation_status", sa.Text(), nullable=False, server_default=sa.text("'confirmed'")),
        sa.Column("provenance", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["source_document_id"], ["household_documents.id"], ondelete="SET NULL", onupdate="CASCADE"),
    )
    op.create_index("idx_household_members_updated_at", "household_members", ["updated_at"], unique=False)
    op.create_index("idx_household_members_source_document_id", "household_members", ["source_document_id"], unique=False)

    op.create_table(
        "household_income_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("owner_name", sa.Text(), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("pay_frequency", sa.Text(), nullable=True),
        sa.Column("employer_or_source", sa.Text(), nullable=True),
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("net_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("monthly_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("annual_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("variable_income_notes", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmation_status", sa.Text(), nullable=False, server_default=sa.text("'confirmed'")),
        sa.Column("provenance", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["source_document_id"], ["household_documents.id"], ondelete="SET NULL", onupdate="CASCADE"),
    )
    op.create_index("idx_household_income_sources_updated_at", "household_income_sources", ["updated_at"], unique=False)
    op.create_index("idx_household_income_sources_source_document_id", "household_income_sources", ["source_document_id"], unique=False)

    op.create_table(
        "household_debt_obligations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("debt_type", sa.Text(), nullable=False),
        sa.Column("lender", sa.Text(), nullable=True),
        sa.Column("balance", sa.Numeric(14, 2), nullable=True),
        sa.Column("monthly_payment", sa.Numeric(12, 2), nullable=True),
        sa.Column("interest_rate", sa.Numeric(6, 3), nullable=True),
        sa.Column("payoff_target_date", sa.Date(), nullable=True),
        sa.Column("secured_by", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmation_status", sa.Text(), nullable=False, server_default=sa.text("'confirmed'")),
        sa.Column("provenance", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["source_document_id"], ["household_documents.id"], ondelete="SET NULL", onupdate="CASCADE"),
    )
    op.create_index("idx_household_debt_obligations_updated_at", "household_debt_obligations", ["updated_at"], unique=False)
    op.create_index("idx_household_debt_obligations_source_document_id", "household_debt_obligations", ["source_document_id"], unique=False)

    op.create_table(
        "household_housing_costs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("housing_type", sa.Text(), nullable=False),
        sa.Column("occupancy_role", sa.Text(), nullable=False, server_default=sa.text("'primary'")),
        sa.Column("monthly_payment", sa.Numeric(12, 2), nullable=True),
        sa.Column("property_tax_monthly", sa.Numeric(12, 2), nullable=True),
        sa.Column("hoa_monthly", sa.Numeric(12, 2), nullable=True),
        sa.Column("insurance_monthly", sa.Numeric(12, 2), nullable=True),
        sa.Column("utilities_monthly", sa.Numeric(12, 2), nullable=True),
        sa.Column("maintenance_monthly", sa.Numeric(12, 2), nullable=True),
        sa.Column("mortgage_balance", sa.Numeric(14, 2), nullable=True),
        sa.Column("interest_rate", sa.Numeric(6, 3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmation_status", sa.Text(), nullable=False, server_default=sa.text("'confirmed'")),
        sa.Column("provenance", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["source_document_id"], ["household_documents.id"], ondelete="SET NULL", onupdate="CASCADE"),
    )
    op.create_index("idx_household_housing_costs_updated_at", "household_housing_costs", ["updated_at"], unique=False)
    op.create_index("idx_household_housing_costs_source_document_id", "household_housing_costs", ["source_document_id"], unique=False)

    op.create_table(
        "household_insurance_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("coverage_type", sa.Text(), nullable=False),
        sa.Column("carrier", sa.Text(), nullable=True),
        sa.Column("premium_monthly", sa.Numeric(12, 2), nullable=True),
        sa.Column("coverage_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("deductible", sa.Numeric(12, 2), nullable=True),
        sa.Column("employer_sponsored", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmation_status", sa.Text(), nullable=False, server_default=sa.text("'confirmed'")),
        sa.Column("provenance", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["source_document_id"], ["household_documents.id"], ondelete="SET NULL", onupdate="CASCADE"),
    )
    op.create_index("idx_household_insurance_policies_updated_at", "household_insurance_policies", ["updated_at"], unique=False)
    op.create_index("idx_household_insurance_policies_source_document_id", "household_insurance_policies", ["source_document_id"], unique=False)

    op.create_table(
        "household_retirement_income_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("owner_name", sa.Text(), nullable=True),
        sa.Column("start_age", sa.Integer(), nullable=True),
        sa.Column("monthly_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("annual_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("inflation_adjusted", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("survivor_benefit", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmation_status", sa.Text(), nullable=False, server_default=sa.text("'confirmed'")),
        sa.Column("provenance", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["source_document_id"], ["household_documents.id"], ondelete="SET NULL", onupdate="CASCADE"),
    )
    op.create_index("idx_household_retirement_income_sources_updated_at", "household_retirement_income_sources", ["updated_at"], unique=False)
    op.create_index("idx_household_retirement_income_sources_source_document_id", "household_retirement_income_sources", ["source_document_id"], unique=False)

    op.create_table(
        "household_planned_expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("expense_kind", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("target_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("monthly_saving_target", sa.Numeric(12, 2), nullable=True),
        sa.Column("priority", sa.Text(), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmation_status", sa.Text(), nullable=False, server_default=sa.text("'confirmed'")),
        sa.Column("provenance", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("evidence_note", sa.Text(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["source_document_id"], ["household_documents.id"], ondelete="SET NULL", onupdate="CASCADE"),
    )
    op.create_index("idx_household_planned_expenses_updated_at", "household_planned_expenses", ["updated_at"], unique=False)
    op.create_index("idx_household_planned_expenses_source_document_id", "household_planned_expenses", ["source_document_id"], unique=False)

    op.create_table(
        "household_document_requirements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("requirement_key", sa.Text(), nullable=False),
        sa.Column("document_kind", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'missing'")),
        sa.Column("priority", sa.Text(), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("related_section", sa.Text(), nullable=True),
        sa.Column("related_record_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'system'")),
        sa.Column("satisfied_by_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["satisfied_by_document_id"], ["household_documents.id"], ondelete="SET NULL", onupdate="CASCADE"),
        sa.UniqueConstraint("requirement_key", name="uq_household_document_requirements_requirement_key"),
    )
    op.create_index("idx_household_document_requirements_status", "household_document_requirements", ["status"], unique=False)
    op.create_index("idx_household_document_requirements_priority", "household_document_requirements", ["priority"], unique=False)
    op.create_index("idx_household_document_requirements_satisfied_by_document_id", "household_document_requirements", ["satisfied_by_document_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_household_document_requirements_satisfied_by_document_id", table_name="household_document_requirements")
    op.drop_index("idx_household_document_requirements_priority", table_name="household_document_requirements")
    op.drop_index("idx_household_document_requirements_status", table_name="household_document_requirements")
    op.drop_table("household_document_requirements")

    op.drop_index("idx_household_planned_expenses_source_document_id", table_name="household_planned_expenses")
    op.drop_index("idx_household_planned_expenses_updated_at", table_name="household_planned_expenses")
    op.drop_table("household_planned_expenses")

    op.drop_index("idx_household_retirement_income_sources_source_document_id", table_name="household_retirement_income_sources")
    op.drop_index("idx_household_retirement_income_sources_updated_at", table_name="household_retirement_income_sources")
    op.drop_table("household_retirement_income_sources")

    op.drop_index("idx_household_insurance_policies_source_document_id", table_name="household_insurance_policies")
    op.drop_index("idx_household_insurance_policies_updated_at", table_name="household_insurance_policies")
    op.drop_table("household_insurance_policies")

    op.drop_index("idx_household_housing_costs_source_document_id", table_name="household_housing_costs")
    op.drop_index("idx_household_housing_costs_updated_at", table_name="household_housing_costs")
    op.drop_table("household_housing_costs")

    op.drop_index("idx_household_debt_obligations_source_document_id", table_name="household_debt_obligations")
    op.drop_index("idx_household_debt_obligations_updated_at", table_name="household_debt_obligations")
    op.drop_table("household_debt_obligations")

    op.drop_index("idx_household_income_sources_source_document_id", table_name="household_income_sources")
    op.drop_index("idx_household_income_sources_updated_at", table_name="household_income_sources")
    op.drop_table("household_income_sources")

    op.drop_index("idx_household_members_source_document_id", table_name="household_members")
    op.drop_index("idx_household_members_updated_at", table_name="household_members")
    op.drop_table("household_members")

    op.drop_column("household_profiles", "emergency_fund_target_amount")
    op.drop_column("household_profiles", "emergency_fund_target_months")
    op.drop_column("household_profiles", "marginal_state_tax_rate")
    op.drop_column("household_profiles", "marginal_federal_tax_rate")
    op.drop_column("household_profiles", "effective_tax_rate")
    op.drop_column("household_profiles", "state_of_residence")
    op.drop_column("household_profiles", "filing_status")
    op.drop_column("household_profiles", "dependent_count")
    op.drop_column("household_profiles", "adult_count")
