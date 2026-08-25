"""Web push to the household's phones — the alert transport D11 chose.

Replaces the shared Telegram chat as the phone sink for money alerts. What that
buys, and the reason the swap was worth making: a push subscription belongs to
one device, so Elias's Pixel and Mariana's Galaxy can be told different things.
``Notifier.send()`` posts to one agent-hub chat with no recipient parameter and
can only ever tell both of them everything.

The payload is encrypted in this process to the browser's own public key, so the
push service (Google's, for both of these phones) relays ciphertext it cannot
read. The VAPID private key signs the request that proves the sender is this
server; it comes from the environment and is never returned by any endpoint.

Nothing here decides *what* is worth pushing — ``spend_alert_service`` does that,
and the alert kinds are 3.7. This module only carries a title and a body to the
devices that asked for them.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pywebpush import WebPushException, webpush

from app.config import settings
from app.logging_config import get_logger
from app.models.push_alerts import (
    PushConfig,
    PushDelivery,
    PushRecipient,
    PushSubscriptionInput,
    PushSubscriptionView,
)
from app.storage import get_storage

logger = get_logger(__name__)

# Time-to-live handed to the push service. A money alert that could not be
# delivered within a day is not news any more — the month has moved on.
PUSH_TTL_SECONDS = 86_400

# Statuses that mean this endpoint is dead for good, not failing right now.
_GONE_STATUSES = frozenset({404, 410})

# The Budget tab's route value is "spending"; the label and the value differ.
_DEFAULT_CLICK_URL = "/money?tab=spending"


@dataclass(frozen=True)
class _Target:
    """One device's row, reduced to what a send needs."""

    id: str
    endpoint: str
    p256dh: str
    auth: str


class PushService:
    def __init__(self) -> None:
        self._storage = get_storage()

    # -- configuration -------------------------------------------------------

    @staticmethod
    def is_configured() -> bool:
        return bool(settings.vapid_private_key and settings.vapid_public_key)

    def config(self) -> PushConfig:
        return PushConfig(
            enabled=self.is_configured(), public_key=settings.vapid_public_key
        )

    # -- recipients ----------------------------------------------------------

    def recipients(self) -> list[PushRecipient]:
        """The adults a device can be registered to (D19).

        Roles, not names, decide who is offered: the household table already
        knows which two members run the budget, so adding a member never means
        editing a list here.
        """
        with self._storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, display_name FROM household_members
                WHERE role IN ('primary', 'spouse')
                ORDER BY created_at
                """,
            ).fetchall()
        return [PushRecipient(id=str(row[0]), name=row[1]) for row in rows]

    # -- subscriptions -------------------------------------------------------

    def list_subscriptions(self) -> list[PushSubscriptionView]:
        with self._storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.household_member_id, m.display_name, s.device_label,
                       s.created_at, s.last_success_at, s.last_failure_at, s.last_error
                FROM household_push_subscriptions s
                LEFT JOIN household_members m ON m.id = s.household_member_id
                ORDER BY m.display_name NULLS LAST, s.created_at
                """,
            ).fetchall()
        return [
            PushSubscriptionView(
                id=str(row[0]),
                household_member_id=str(row[1]) if row[1] else None,
                member_name=row[2],
                device_label=row[3],
                created_at=_iso(row[4]),
                last_success_at=_iso(row[5]),
                last_failure_at=_iso(row[6]),
                last_error=row[7],
            )
            for row in rows
        ]

    def register(self, payload: PushSubscriptionInput) -> PushSubscriptionView:
        """Upsert one device.

        A browser can hand back the same endpoint after a permission re-grant,
        after a reinstall, or simply on a second visit, so the endpoint decides
        identity: re-registering updates whose phone it is instead of leaving a
        second row that pushes the same alert to the same handset twice.
        """
        with self._storage.connection() as conn:
            row = conn.execute(
                """
                INSERT INTO household_push_subscriptions
                    (id, household_member_id, endpoint, p256dh, auth, device_label, user_agent)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (endpoint) DO UPDATE
                SET household_member_id = EXCLUDED.household_member_id,
                    p256dh = EXCLUDED.p256dh,
                    auth = EXCLUDED.auth,
                    device_label = EXCLUDED.device_label,
                    user_agent = EXCLUDED.user_agent,
                    updated_at = now()
                RETURNING id
                """,
                [
                    str(uuid.uuid4()),
                    payload.household_member_id,
                    payload.endpoint,
                    payload.keys.encryption_key,
                    payload.keys.auth_secret,
                    payload.device_label,
                    payload.user_agent,
                ],
            ).fetchone()
            conn.commit()
        subscription_id = str(row[0]) if row else ""
        logger.info("push_subscription_registered", subscription_id=subscription_id)
        return next(
            (s for s in self.list_subscriptions() if s.id == subscription_id),
            PushSubscriptionView(id=subscription_id),
        )

    def unregister(self, subscription_id: str) -> bool:
        with self._storage.connection() as conn:
            row = conn.execute(
                "DELETE FROM household_push_subscriptions WHERE id = %s RETURNING id",
                [subscription_id],
            ).fetchone()
            conn.commit()
        return row is not None

    def unregister_endpoint(self, endpoint: str) -> bool:
        """Used when a device turns alerts off on the device itself."""
        with self._storage.connection() as conn:
            row = conn.execute(
                "DELETE FROM household_push_subscriptions WHERE endpoint = %s RETURNING id",
                [endpoint],
            ).fetchone()
            conn.commit()
        return row is not None

    # -- sending -------------------------------------------------------------

    def send(
        self,
        *,
        title: str,
        body: str,
        severity: str = "info",
        url: str = _DEFAULT_CLICK_URL,
        tag: str | None = None,
        subscription_id: str | None = None,
        household_member_ids: list[str] | None = None,
    ) -> PushDelivery:
        """Deliver one alert to the matching devices.

        ``tag`` is passed through to ``showNotification`` so a second push about
        the same crossing replaces the first in the tray rather than stacking a
        duplicate under it.
        """
        if not self.is_configured():
            logger.info("push_not_configured", title=title)
            return PushDelivery()

        targets = self._targets(
            subscription_id=subscription_id, household_member_ids=household_member_ids
        )
        if not targets:
            return PushDelivery()

        payload = json.dumps(
            {
                "title": title,
                "body": body,
                "severity": severity,
                "url": url,
                "tag": tag or "portfolio-ai-alert",
            }
        )
        delivery = PushDelivery()
        for target in targets:
            status = self._send_one(target, payload)
            if status == "delivered":
                delivery.delivered += 1
            elif status == "expired":
                delivery.expired += 1
            else:
                delivery.failed += 1
        logger.info(
            "push_dispatched",
            title=title,
            delivered=delivery.delivered,
            failed=delivery.failed,
            expired=delivery.expired,
        )
        return delivery

    def _send_one(self, target: _Target, payload: str) -> str:
        try:
            webpush(
                subscription_info={
                    "endpoint": target.endpoint,
                    "keys": {"p256dh": target.p256dh, "auth": target.auth},
                },
                data=payload,
                vapid_private_key=settings.vapid_private_key,
                # pywebpush fills in `aud` and `exp` on this dict in place, so
                # each send gets its own: a reused dict would keep the first
                # endpoint's audience and every later push would be rejected.
                vapid_claims={"sub": settings.vapid_subject},
                ttl=PUSH_TTL_SECONDS,
            )
        except WebPushException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in _GONE_STATUSES:
                self.unregister(target.id)
                logger.info(
                    "push_subscription_expired",
                    subscription_id=target.id,
                    status=status,
                )
                return "expired"
            self._mark_failure(target.id, f"{status or 'error'}: {exc}")
            logger.warning(
                "push_send_failed", subscription_id=target.id, status=status
            )
            return "failed"
        except Exception as exc:  # one dead device must not stop the rest
            self._mark_failure(target.id, str(exc))
            logger.warning("push_send_error", subscription_id=target.id, exc_info=True)
            return "failed"
        self._mark_success(target.id)
        return "delivered"

    # -- data access ---------------------------------------------------------

    def _targets(
        self,
        *,
        subscription_id: str | None = None,
        household_member_ids: list[str] | None = None,
    ) -> list[_Target]:
        sql = "SELECT id, endpoint, p256dh, auth FROM household_push_subscriptions"
        params: list[Any] = []
        if subscription_id:
            sql += " WHERE id = %s"
            params.append(subscription_id)
        elif household_member_ids:
            sql += " WHERE household_member_id = ANY(%s)"
            params.append(list(household_member_ids))
        with self._storage.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            _Target(id=str(row[0]), endpoint=row[1], p256dh=row[2], auth=row[3])
            for row in rows
        ]

    def _mark_success(self, subscription_id: str) -> None:
        with self._storage.connection() as conn:
            conn.execute(
                """
                UPDATE household_push_subscriptions
                SET last_success_at = %s, last_error = NULL, updated_at = now()
                WHERE id = %s
                """,
                [datetime.now(UTC), subscription_id],
            )
            conn.commit()

    def _mark_failure(self, subscription_id: str, error: str) -> None:
        with self._storage.connection() as conn:
            conn.execute(
                """
                UPDATE household_push_subscriptions
                SET last_failure_at = %s, last_error = %s, updated_at = now()
                WHERE id = %s
                """,
                [datetime.now(UTC), error[:500], subscription_id],
            )
            conn.commit()


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def send_push(
    *,
    title: str,
    body: str,
    severity: str = "info",
    url: str = _DEFAULT_CLICK_URL,
    tag: str | None = None,
) -> PushDelivery:
    """Module-level convenience for alert call sites."""
    return PushService().send(
        title=title, body=body, severity=severity, url=url, tag=tag
    )
