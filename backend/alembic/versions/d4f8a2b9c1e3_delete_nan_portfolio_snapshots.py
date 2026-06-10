"""delete NaN portfolio snapshot rows

Revision ID: d4f8a2b9c1e3
Revises: b3d9e1c4a7f2
Create Date: 2026-06-10 00:00:00.000000

NaN values stored in numeric columns panic polars (pyo3 PanicException)
on every query that reads them, and sort above all real values in
ORDER BY equity DESC, corrupting peak-equity lookups. Writes are now
guarded in save_portfolio_snapshot; this removes the existing bad rows.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f8a2b9c1e3"
down_revision: str | Sequence[str] | None = "b3d9e1c4a7f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Delete snapshot rows containing NaN in any numeric column."""
    op.execute(
        """
        DELETE FROM portfolio_snapshots
        WHERE equity = 'NaN'::numeric
           OR cash = 'NaN'::numeric
           OR position_value = 'NaN'::numeric
           OR peak_equity = 'NaN'::numeric
           OR drawdown_pct = 'NaN'::numeric
        """
    )


def downgrade() -> None:
    """No-op: deleted rows contained no recoverable data."""
