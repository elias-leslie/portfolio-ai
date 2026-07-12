"""record Hatchet runtime status with worker heartbeats

Revision ID: f825742b0002
Revises: a6b7c8d9e0f1
Create Date: 2026-07-12 14:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f825742b0002"
down_revision: str | Sequence[str] | None = "a6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT_NAME = "service_heartbeats_reported_status_valid"


def upgrade() -> None:
    """Add a fail-closed Hatchet runtime state to each heartbeat."""
    op.execute(
        """
        ALTER TABLE service_heartbeats
        ADD COLUMN reported_status TEXT NOT NULL DEFAULT 'starting'
        """
    )
    op.execute("ALTER TABLE service_heartbeats ALTER COLUMN reported_status DROP DEFAULT")
    op.create_check_constraint(
        _CONSTRAINT_NAME,
        "service_heartbeats",
        "reported_status IN ('starting', 'healthy', 'unhealthy')",
    )


def downgrade() -> None:
    """Remove the Hatchet runtime state from heartbeats."""
    op.drop_constraint(_CONSTRAINT_NAME, "service_heartbeats", type_="check")
    op.drop_column("service_heartbeats", "reported_status")
