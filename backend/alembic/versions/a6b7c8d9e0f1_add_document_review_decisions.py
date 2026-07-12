"""persist typed document reviews and one-time user decisions

Revision ID: a6b7c8d9e0f1
Revises: f4a5b6c7d8e9
Create Date: 2026-07-12 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a6b7c8d9e0f1"
down_revision: str | Sequence[str] | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the complete review envelope and auditable decision state."""
    op.add_column(
        "household_document_reviews",
        sa.Column(
            "review_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "household_document_reviews",
        sa.Column("decision", sa.Text(), nullable=True),
    )
    op.add_column(
        "household_document_reviews",
        sa.Column("decision_status", sa.Text(), nullable=True),
    )
    op.add_column(
        "household_document_reviews",
        sa.Column("decision_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "household_document_reviews",
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "household_document_reviews",
        sa.Column(
            "decision_application_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_household_document_reviews_decision",
        "household_document_reviews",
        "decision IS NULL OR decision IN ('approve', 'reject')",
    )
    op.create_check_constraint(
        "ck_household_document_reviews_decision_status",
        "household_document_reviews",
        "decision_status IS NULL OR decision_status IN "
        "('applying', 'applied', 'rejected', 'failed')",
    )
    op.create_check_constraint(
        "ck_household_document_reviews_decision_pair",
        "household_document_reviews",
        "(decision IS NULL AND decision_status IS NULL) OR "
        "(decision = 'approve' AND decision_status IN ('applying', 'applied', 'failed')) OR "
        "(decision = 'reject' AND decision_status = 'rejected')",
    )


def downgrade() -> None:
    """Remove review-decision persistence."""
    op.drop_constraint(
        "ck_household_document_reviews_decision_pair",
        "household_document_reviews",
        type_="check",
    )
    op.drop_constraint(
        "ck_household_document_reviews_decision_status",
        "household_document_reviews",
        type_="check",
    )
    op.drop_constraint(
        "ck_household_document_reviews_decision",
        "household_document_reviews",
        type_="check",
    )
    op.drop_column("household_document_reviews", "decision_application_summary")
    op.drop_column("household_document_reviews", "decided_at")
    op.drop_column("household_document_reviews", "decision_reason")
    op.drop_column("household_document_reviews", "decision_status")
    op.drop_column("household_document_reviews", "decision")
    op.drop_column("household_document_reviews", "review_payload")
