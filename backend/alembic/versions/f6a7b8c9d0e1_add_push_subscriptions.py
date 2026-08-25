"""hold one row per phone that has said yes to alerts

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-25 10:10:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """A push subscription is a device, not a person, so the device is the row.

    The browser mints the endpoint; it is the identity the push service knows
    and the only thing that can be deduplicated on, so it carries the unique
    constraint. ``household_member_id`` is who that phone belongs to — the
    routing D11 wanted and the shared Telegram chat could not give: Elias's
    Pixel and Mariana's Galaxy subscribe separately, so an alert can go to one
    of them without going to both.

    ``p256dh`` and ``auth`` are the browser's public encryption material, not
    secrets of ours; the payload is encrypted to them so the push service
    carries ciphertext it cannot read.
    """
    op.execute(
        """
        CREATE TABLE household_push_subscriptions (
            id UUID PRIMARY KEY,
            household_member_id UUID REFERENCES household_members(id) ON DELETE CASCADE,
            endpoint TEXT NOT NULL UNIQUE,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            device_label TEXT,
            user_agent TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_success_at TIMESTAMPTZ,
            last_failure_at TIMESTAMPTZ,
            last_error TEXT
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_household_push_subscriptions_member
        ON household_push_subscriptions (household_member_id)
        """
    )


def downgrade() -> None:
    """Drop the devices. Each one re-subscribes by granting permission again."""
    op.execute("DROP TABLE household_push_subscriptions")
