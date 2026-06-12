"""Add item-level purchase tracking tables.

Revision ID: a9c4e7f2b1d8
Revises: d8f3a6b2c9e4
Create Date: 2026-06-12 19:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a9c4e7f2b1d8"
down_revision: str | Sequence[str] | None = "d8f3a6b2c9e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    ]


def _jsonb_metadata() -> sa.Column:
    return sa.Column(
        "metadata",
        postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    )


def upgrade() -> None:
    op.create_table(
        "household_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("package_display_label", sa.Text(), nullable=True),
        sa.Column("package_normalized_quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("package_normalized_unit", sa.String(length=32), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("watched", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        _jsonb_metadata(),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "household_product_identifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["product_id"], ["household_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "value", name="uq_household_product_identifiers_kind_value"),
    )
    op.create_index(
        "idx_household_product_identifiers_product_id",
        "household_product_identifiers",
        ["product_id"],
    )

    op.create_table(
        "household_purchase_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_row_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("purchase_group_key", sa.Text(), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "product_match_status",
            sa.String(length=32),
            nullable=False,
            server_default="unmatched",
        ),
        sa.Column("product_match_confidence", sa.Float(), nullable=True),
        sa.Column("purchase_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("essentiality", sa.Text(), nullable=False),
        sa.Column(
            "categorization_source",
            sa.String(length=32),
            nullable=False,
            server_default="parser",
        ),
        sa.Column("item_rule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("removed", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        _jsonb_metadata(),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["import_row_id"], ["household_import_rows.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["document_id"], ["household_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["household_transactions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["merchant_id"], ["household_merchants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["household_products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["item_rule_id"], ["household_transaction_rules.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_row_id", name="uq_household_purchase_items_import_row_id"),
    )
    op.create_index(
        "idx_household_purchase_items_transaction_id",
        "household_purchase_items",
        ["transaction_id"],
    )
    op.create_index(
        "idx_household_purchase_items_purchase_group_key",
        "household_purchase_items",
        ["purchase_group_key"],
    )
    op.create_index(
        "idx_household_purchase_items_product_id",
        "household_purchase_items",
        ["product_id"],
    )
    op.create_index(
        "idx_household_purchase_items_product_match_status",
        "household_purchase_items",
        ["product_match_status"],
    )

    op.create_table(
        "household_product_price_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("observed_date", sa.Date(), nullable=False),
        sa.Column("total_price", sa.Numeric(18, 2), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("package_display_label", sa.Text(), nullable=True),
        sa.Column("package_normalized_quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("package_normalized_unit", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        _jsonb_metadata(),
        *_timestamps(),
        sa.ForeignKeyConstraint(["product_id"], ["household_products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["purchase_item_id"], ["household_purchase_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["merchant_id"], ["household_merchants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_household_product_price_observations_product_date",
        "household_product_price_observations",
        ["product_id", "observed_date"],
    )
    op.create_index(
        "uq_household_product_price_observations_purchase_item",
        "household_product_price_observations",
        ["purchase_item_id"],
        unique=True,
        postgresql_where=sa.text("purchase_item_id IS NOT NULL"),
    )

    op.create_table(
        "household_price_check_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("triggered_by", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column(
            "vendor_status",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("product_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quote_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("finding_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        _jsonb_metadata(),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "household_shopping_lists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "latest_optimization",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        _jsonb_metadata(),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "household_shopping_list_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shopping_list_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("free_text", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        _jsonb_metadata(),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["shopping_list_id"], ["household_shopping_lists.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["household_products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_household_shopping_list_items_list_id",
        "household_shopping_list_items",
        ["shopping_list_id"],
    )

    op.create_table(
        "household_vendor_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("delivery_fee", sa.Numeric(18, 2), nullable=True),
        sa.Column("pickup_fee", sa.Numeric(18, 2), nullable=True),
        sa.Column("free_delivery_threshold", sa.Numeric(18, 2), nullable=True),
        sa.Column("membership_monthly_fee", sa.Numeric(18, 2), nullable=True),
        sa.Column(
            "membership_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        _jsonb_metadata(),
        *_timestamps(),
        sa.ForeignKeyConstraint(["merchant_id"], ["household_merchants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vendor_key", name="uq_household_vendor_profiles_vendor_key"),
    )

    op.create_table(
        "household_price_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("shopping_list_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("merchant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("vendor_key", sa.String(length=64), nullable=True),
        sa.Column("price_check_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("savings_estimate", sa.Numeric(18, 2), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(["product_id"], ["household_products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["shopping_list_id"], ["household_shopping_lists.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["merchant_id"], ["household_merchants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["price_check_run_id"], ["household_price_check_runs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_household_price_findings_status",
        "household_price_findings",
        ["status"],
    )
    op.create_index(
        "idx_household_price_findings_product_id",
        "household_price_findings",
        ["product_id"],
    )

    op.add_column(
        "household_transaction_rules",
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_household_transaction_rules_product_id",
        "household_transaction_rules",
        "household_products",
        ["product_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "uq_household_transaction_rules_active_product",
        "household_transaction_rules",
        ["product_id"],
        unique=True,
        postgresql_where=sa.text("enabled IS TRUE AND product_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_household_transaction_rules_active_product",
        table_name="household_transaction_rules",
    )
    op.drop_constraint(
        "fk_household_transaction_rules_product_id",
        "household_transaction_rules",
        type_="foreignkey",
    )
    op.drop_column("household_transaction_rules", "product_id")
    op.drop_table("household_price_findings")
    op.drop_table("household_vendor_profiles")
    op.drop_table("household_shopping_list_items")
    op.drop_table("household_shopping_lists")
    op.drop_table("household_price_check_runs")
    op.drop_table("household_product_price_observations")
    op.drop_table("household_purchase_items")
    op.drop_table("household_product_identifiers")
    op.drop_table("household_products")
