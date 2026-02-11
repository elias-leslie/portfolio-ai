"""baseline schema from custom migrations

Revision ID: 98d4e5d9fce7
Revises: 
Create Date: 2026-02-08 11:46:32.293538

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '98d4e5d9fce7'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
