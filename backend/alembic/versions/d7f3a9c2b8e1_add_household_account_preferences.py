"""add household account preferences

Revision ID: d7f3a9c2b8e1
Revises: b1f6a24c9d3e
Create Date: 2026-05-03 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d7f3a9c2b8e1"
down_revision: str | Sequence[str] | None = "b1f6a24c9d3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "household_account_preferences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("household_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_label", sa.String(length=255), nullable=True),
        sa.Column("display_owner_name", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.ForeignKeyConstraint(["household_account_id"], ["household_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_household_account_preferences_household_account_id",
        "household_account_preferences",
        ["household_account_id"],
        unique=True,
    )
    op.create_index(
        "idx_household_account_preferences_updated_at",
        "household_account_preferences",
        [sa.text("updated_at DESC")],
        unique=False,
    )
    op.execute(
        """
        INSERT INTO household_account_preferences (
            household_account_id,
            display_label,
            display_owner_name,
            notes,
            created_at,
            updated_at
        )
        SELECT
            household_account_id,
            NULLIF(label, ''),
            NULLIF(owner_name, ''),
            NULLIF(notes, ''),
            MIN(created_at),
            MAX(updated_at)
        FROM household_tracked_accounts
        WHERE household_account_id IS NOT NULL
        GROUP BY household_account_id, NULLIF(label, ''), NULLIF(owner_name, ''), NULLIF(notes, '')
        ON CONFLICT (household_account_id) DO UPDATE
        SET display_label = EXCLUDED.display_label,
            display_owner_name = EXCLUDED.display_owner_name,
            notes = EXCLUDED.notes,
            updated_at = EXCLUDED.updated_at
        """
    )
    op.execute("DELETE FROM household_tracked_accounts WHERE household_account_id IS NOT NULL")


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO household_tracked_accounts (
            id, household_account_id, label, asset_group, account_type, source_type,
            match_key, institution_name, owner_name, account_mask, notes,
            created_at, updated_at
        )
        SELECT
            p.id,
            p.household_account_id,
            COALESCE(NULLIF(p.display_label, ''), a.canonical_label),
            a.asset_group,
            a.account_type,
            a.source_type,
            a.primary_identity_key,
            a.institution_name,
            COALESCE(NULLIF(p.display_owner_name, ''), a.owner_name),
            a.account_mask,
            p.notes,
            p.created_at,
            p.updated_at
        FROM household_account_preferences p
        JOIN household_accounts a ON a.id = p.household_account_id
        WHERE p.hidden_at IS NULL
        ON CONFLICT (id) DO NOTHING
        """
    )
    op.drop_index(
        "idx_household_account_preferences_updated_at",
        table_name="household_account_preferences",
    )
    op.drop_index(
        "uq_household_account_preferences_household_account_id",
        table_name="household_account_preferences",
    )
    op.drop_table("household_account_preferences")
