"""add household question formats

Revision ID: 5ce02b41a5a8
Revises: 22358991bf43
Create Date: 2026-03-11 17:05:34.242456

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5ce02b41a5a8'
down_revision: str | Sequence[str] | None = '22358991bf43'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "household_questions",
        sa.Column(
            "question_format",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'short_text'"),
        ),
    )
    op.add_column(
        "household_questions",
        sa.Column(
            "options",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "household_questions",
        sa.Column(
            "direction",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'jenny_to_user'"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("household_questions", "direction")
    op.drop_column("household_questions", "options")
    op.drop_column("household_questions", "question_format")
