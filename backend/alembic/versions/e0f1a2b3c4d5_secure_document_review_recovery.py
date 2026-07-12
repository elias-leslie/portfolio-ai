"""secure document review previews and resumable approvals

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-07-12 21:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e0f1a2b3c4d5"
down_revision: str | Sequence[str] | None = "d9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Persist proposal bindings and an exclusive, resumable apply journal."""
    op.add_column(
        "household_document_reviews",
        sa.Column("proposal_hash", sa.Text(), nullable=True),
    )
    op.add_column(
        "household_document_reviews",
        sa.Column(
            "proposal_preview",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "household_document_reviews",
        sa.Column("application_phase", sa.Text(), nullable=True),
    )
    op.add_column(
        "household_document_reviews",
        sa.Column(
            "application_journal",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "household_document_reviews",
        sa.Column(
            "application_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "household_document_reviews",
        sa.Column("application_executor_token", sa.Text(), nullable=True),
    )
    op.add_column(
        "household_document_reviews",
        sa.Column("application_last_error", sa.Text(), nullable=True),
    )

    op.create_check_constraint(
        "ck_household_document_reviews_proposal_hash",
        "household_document_reviews",
        "proposal_hash IS NULL OR proposal_hash ~ '^[0-9a-f]{64}$'",
    )
    op.create_check_constraint(
        "ck_household_document_reviews_proposal_binding",
        "household_document_reviews",
        "(proposal_hash IS NULL AND proposal_preview IS NULL) OR "
        "(proposal_hash IS NOT NULL AND proposal_preview IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_household_document_reviews_application_phase",
        "household_document_reviews",
        "application_phase IS NULL OR application_phase IN "
        "('claimed', 'outputs_applied', 'inferences_applied', 'finalized')",
    )
    op.create_check_constraint(
        "ck_household_document_reviews_application_attempts",
        "household_document_reviews",
        "application_attempts >= 0",
    )

    # Schema-v1 proposals never exposed the exact values being approved and
    # have no cryptographic binding. Keep their audit rows, but force a new
    # review before another user decision can mutate money data.
    op.execute(
        """
        UPDATE household_documents
        SET metadata = jsonb_set(
            jsonb_set(
                COALESCE(metadata, '{}'::jsonb),
                '{review_proposal,status}',
                '"stale"'::jsonb,
                TRUE
            ),
            '{review_proposal,blocker}',
            to_jsonb(
                'This older proposal must be re-reviewed before it can be approved.'::text
            ),
            TRUE
        )
        WHERE metadata->'review_proposal'->>'status' IN ('pending', 'applying', 'failed')
          AND COALESCE(metadata->'review_proposal'->>'schema_version', '1') <> '2'
        """
    )
    op.execute(
        """
        UPDATE household_document_reviews
        SET decision_status = 'failed',
            application_last_error =
                'Legacy unbound approval requires a fresh document review.',
            updated_at = CURRENT_TIMESTAMP
        WHERE decision = 'approve'
          AND decision_status = 'applying'
          AND proposal_hash IS NULL
        """
    )


def downgrade() -> None:
    """Remove resumable approval state; stale proposal metadata remains safe."""
    op.drop_constraint(
        "ck_household_document_reviews_application_attempts",
        "household_document_reviews",
        type_="check",
    )
    op.drop_constraint(
        "ck_household_document_reviews_application_phase",
        "household_document_reviews",
        type_="check",
    )
    op.drop_constraint(
        "ck_household_document_reviews_proposal_binding",
        "household_document_reviews",
        type_="check",
    )
    op.drop_constraint(
        "ck_household_document_reviews_proposal_hash",
        "household_document_reviews",
        type_="check",
    )
    op.drop_column("household_document_reviews", "application_last_error")
    op.drop_column("household_document_reviews", "application_executor_token")
    op.drop_column("household_document_reviews", "application_attempts")
    op.drop_column("household_document_reviews", "application_journal")
    op.drop_column("household_document_reviews", "application_phase")
    op.drop_column("household_document_reviews", "proposal_preview")
    op.drop_column("household_document_reviews", "proposal_hash")
