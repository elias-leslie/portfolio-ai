"""add social security payable ratio

Revision ID: f1a2b3c4d5e6
Revises: e9b8c7d6a5f4
Create Date: 2026-05-26 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e9b8c7d6a5f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("household_profiles", sa.Column("social_security_payable_ratio", sa.Numeric(6, 5), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("household_profiles", "social_security_payable_ratio")
