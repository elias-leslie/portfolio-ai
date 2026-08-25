"""One finding, two sinks, one interrupt per crossing (plan §0a, D11).

Every alert in this system is dispatched the same way, and the shape is the
part worth reusing rather than the alert kinds:

1. a **sent marker** decides whether this crossing has already interrupted
   anyone, so soft charges nudging a total upward do not re-push the same
   finding all afternoon;
2. ``jenny_notifications`` takes it for the UI, deduped by open-notification
   upsert;
3. **web push** takes it for the phones that registered (3.6), with the marker
   passed through as the tray tag so a repeat replaces its own entry;
4. the shared agent-hub chat takes it **only when no phone did**, because
   swapping a transport must not open a window where a finding reaches nobody.

Marker keys are namespaced by ``marker_prefix`` so two producers cannot collide
on one: the card kinds and the plan kinds are counted separately even when both
are about the same month.

``jenny_notifications.routine_id`` is a foreign key into ``jenny_routines``, and
an alert producer is a synthetic routine that never runs through the coordinator
which normally creates that row. Without one every write raised a foreign-key
violation which each caller then swallowed as ``{"status": "error"}`` — so the
card alerts wrote nothing, pushed nothing and left no marker from the day they
shipped, silently. ``_ensure_routine_row`` closes that: the routine is upserted
before the first notification of a pass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from app.logging_config import get_logger
from app.services._jenny_review_notifications import (
    _normalize_routine_id,
    upsert_notification,
)
from app.services.notifier_service import get_notifier
from app.services.push_service import PushService
from app.storage import get_storage

logger = get_logger(__name__)

# Where a pushed alert opens. The plan is the screen that answers "and now
# what?", so a tapped notification lands there rather than on the app's home.
# The Budget tab's route value is "spending" — the label and the value differ.
ALERT_CLICK_URL = "/money?tab=spending"


@dataclass
class Alert:
    kind: str
    severity: str  # info | warning | critical
    title: str
    body: str
    marker_key: str  # dedupe key — one interrupt per crossing
    # What the alert is about, when the kind alone does not say. It is appended
    # to the notification category, because that is the field the UI sink
    # deduplicates on: three categories over their caps are three rows, where
    # without it the third would overwrite the first two and the inbox would
    # show one of them. It cannot go in the ``symbol`` column instead — that one
    # is a foreign key into ``symbols`` and only ever holds a real ticker.
    subject: str | None = None


class _StorageShim:
    """upsert_notification expects an object with .storage."""

    def __init__(self) -> None:
        self.storage = get_storage()


def already_sent(marker_key: str, *, marker_prefix: str) -> bool:
    with get_storage().connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM household_confirmed_facts WHERE fact_key = %s",
            [f"{marker_prefix}:{marker_key}"],
        ).fetchone()
    return row is not None


def mark_sent(marker_key: str, *, marker_prefix: str) -> None:
    with get_storage().connection() as conn:
        conn.execute(
            """
            INSERT INTO household_confirmed_facts (fact_key, fact_value, confirmed_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (fact_key) DO UPDATE
            SET fact_value = EXCLUDED.fact_value, confirmed_at = EXCLUDED.confirmed_at
            """,
            [f"{marker_prefix}:{marker_key}", datetime.now(UTC).isoformat()],
        )
        conn.commit()


def _notification_category(prefix: str, alert: Alert) -> str:
    """One open notification per thing the alert is about, not per kind."""
    base = f"{prefix}{alert.kind}"
    return f"{base}:{alert.subject}" if alert.subject else base


def _ensure_routine_row(routine_id: str, *, routine_type: str) -> None:
    """Make the synthetic routine real enough for the notification foreign key.

    Idempotent: the row is one per producer, not one per pass, so the alert
    history stays attached to a single routine the UI can group under. The id is
    derived with the notification helper's own normalizer, because a row keyed
    any other way would satisfy nothing — the foreign key is checked against the
    uuid5 that helper writes.
    """
    with get_storage().connection() as conn:
        conn.execute(
            """
            INSERT INTO jenny_routines (
                id, routine_type, status, triggered_by, started_at, completed_at,
                agents_used, metadata
            ) VALUES (%s, %s, 'completed', 'system', %s, %s, %s::jsonb, %s::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            [
                _normalize_routine_id(routine_id),
                routine_type,
                datetime.now(UTC),
                datetime.now(UTC),
                json.dumps([]),
                json.dumps({"synthetic": True, "source": routine_type}),
            ],
        )
        conn.commit()


def dispatch_alerts(
    alerts: list[Alert],
    *,
    routine_id: str,
    routine_type: str,
    marker_prefix: str,
    trigger: str,
    category_prefix: str = "",
) -> list[Alert]:
    """Send the alerts nobody has been told about yet. Returns what went out."""
    dispatched: list[Alert] = []
    pending = [
        alert
        for alert in alerts
        if not already_sent(alert.marker_key, marker_prefix=marker_prefix)
    ]
    if not pending:
        return []

    _ensure_routine_row(routine_id, routine_type=routine_type)
    notifier = get_notifier()
    push = PushService()
    shim = _StorageShim()
    for alert in pending:
        upsert_notification(
            shim,
            routine_id,
            None,
            category=_notification_category(category_prefix, alert),
            severity=alert.severity,
            title=alert.title,
            detail=alert.body,
            recommendation=None,
        )
        delivery = push.send(
            title=alert.title,
            body=alert.body,
            severity=alert.severity,
            url=ALERT_CLICK_URL,
            tag=alert.marker_key,
        )
        if delivery.delivered == 0:
            # No phone took it — registered devices are how this reaches a
            # person, so the shared chat stays the sink until one has.
            notifier.send(title=alert.title, body=alert.body, severity=alert.severity)
        mark_sent(alert.marker_key, marker_prefix=marker_prefix)
        dispatched.append(alert)
    if dispatched:
        logger.info(
            "alerts_dispatched",
            routine=routine_id,
            trigger=trigger,
            kinds=[alert.kind for alert in dispatched],
        )
    return dispatched
