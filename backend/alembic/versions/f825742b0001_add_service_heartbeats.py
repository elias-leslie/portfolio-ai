"""add persisted service heartbeats

Revision ID: f825742b0001
Revises: c1d2e3f4a5b6
Create Date: 2026-07-12 14:20:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f825742b0001"
down_revision: str | Sequence[str] | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the cross-process service heartbeat registry."""
    op.execute(
        """
        CREATE TABLE service_heartbeats (
            service_name TEXT PRIMARY KEY,
            instance_id UUID NOT NULL,
            hostname TEXT NOT NULL,
            pid INTEGER NOT NULL CHECK (pid > 0),
            started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT service_heartbeats_name_not_blank
                CHECK (BTRIM(service_name) <> ''),
            CONSTRAINT service_heartbeats_hostname_not_blank
                CHECK (BTRIM(hostname) <> '')
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE service_heartbeats IS
            'Database-backed liveness signals shared by native and container services'
        """
    )


def downgrade() -> None:
    """Remove the service heartbeat registry."""
    op.execute("DROP TABLE service_heartbeats")
