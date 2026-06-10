"""Card spend/rotation alerts — one evaluation, two sinks (plan §8 + §0a).

``evaluate_and_dispatch()`` reads the canonical ledger (so soft + pending +
hard charges all count, per the §5 mirror-row design) and the owned-card state,
then emits each finding to BOTH:

- ``jenny_notifications`` (UI, deduped by open-notification upsert), and
- the Telegram notifier (phone push, throttled by a sent-marker so each alert
  pushes at most once per crossing — no spam when soft charges keep nudging).

Alert kinds (user-locked 2026-06-10): monthly spend pace vs the card cap,
welcome-bonus (MSR) deadline risk, rotation action due, annual-fee renewal
(with downgrade-not-cancel guidance), and material catalog changes from the
research agent. Only findings that affect money interrupt ([G:2d62382d]).

Welcome (MSR) progress is refreshed here from ledger rows of the card's linked
account since ``opened_date`` — the tracker the user asked for ("many cards
require spending X within Y days").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from app.logging_config import get_logger
from app.services._jenny_review_notifications import upsert_notification
from app.services.notifier_service import get_notifier
from app.storage import get_storage

logger = get_logger(__name__)

# Stable synthetic routine id for jenny_notifications rows from this service.
CARD_ALERT_ROUTINE_ID = "card-spend-alerts"

DEFAULT_MONTHLY_CAP = 6500.0
# Push when month-to-date crosses this fraction of the cap, again at the cap.
WARN_THRESHOLD_PCT = 0.85
ROTATION_DUE_DAYS = 90
ANNUAL_FEE_LOOKAHEAD_DAYS = 30

_MARKER_PREFIX = "card_alert_sent"


@dataclass
class SpendAlert:
    kind: str
    severity: str  # info | warning | critical
    title: str
    body: str
    marker_key: str  # dedupe key — one push per crossing


class _StorageShim:
    """upsert_notification expects an object with .storage."""

    def __init__(self) -> None:
        self.storage = get_storage()


class SpendAlertService:
    def __init__(self) -> None:
        self._storage = get_storage()

    def evaluate_and_dispatch(
        self, *, trigger: str, catalog_changes: list[dict[str, Any]] | None = None
    ) -> list[SpendAlert]:
        """Refresh welcome progress, evaluate all alert kinds, dispatch new ones."""
        alerts: list[SpendAlert] = []
        try:
            self.refresh_welcome_progress()
        except Exception:
            logger.warning("welcome_progress_refresh_failed", exc_info=True)
        cards = self._owned_cards()
        alerts.extend(self._pace_alerts(cards))
        alerts.extend(self._welcome_alerts(cards))
        alerts.extend(self._rotation_alerts(cards))
        alerts.extend(self._annual_fee_alerts(cards))
        alerts.extend(self._catalog_alerts(catalog_changes or []))

        dispatched: list[SpendAlert] = []
        notifier = get_notifier()
        shim = _StorageShim()
        for alert in alerts:
            if self._already_sent(alert.marker_key):
                continue
            upsert_notification(
                shim,
                CARD_ALERT_ROUTINE_ID,
                None,
                category=f"card_{alert.kind}",
                severity=alert.severity,
                title=alert.title,
                detail=alert.body,
                recommendation=None,
            )
            notifier.send(title=alert.title, body=alert.body, severity=alert.severity)
            self._mark_sent(alert.marker_key)
            dispatched.append(alert)
        if dispatched:
            logger.info(
                "card_alerts_dispatched",
                trigger=trigger,
                kinds=[a.kind for a in dispatched],
            )
        return dispatched

    # -- welcome (MSR) progress tracker -------------------------------------

    def refresh_welcome_progress(self) -> int:
        """Recompute welcome_progress_amount from the linked account's ledger
        rows since opened_date; advance welcome_status. Returns rows updated."""
        updated = 0
        with self._storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.household_account_id, c.opened_date, c.welcome_deadline,
                       c.welcome_status, p.welcome_min_spend
                FROM household_credit_cards c
                JOIN credit_card_products p ON p.id = c.product_id
                WHERE c.status = 'active'
                  AND c.household_account_id IS NOT NULL
                  AND c.opened_date IS NOT NULL
                  AND COALESCE(p.welcome_min_spend, 0) > 0
                  AND c.welcome_status IN ('not_started', 'in_progress')
                """,
            ).fetchall()
            today = datetime.now(UTC).date()
            for card_id, account_id, opened, deadline, _status, raw_min_spend in rows:
                spend_row = conn.execute(
                    """
                    SELECT COALESCE(SUM(amount), 0)
                    FROM household_transactions
                    WHERE household_account_id = %s
                      AND flow_type = 'expense' AND removed = FALSE
                      AND transaction_date >= %s
                    """,
                    [account_id, opened],
                ).fetchone()
                progress = float((spend_row[0] if spend_row else 0) or 0.0)
                min_spend = float(raw_min_spend or 0.0)
                deadline_date = deadline if isinstance(deadline, date) else None
                if progress >= min_spend:
                    status = "earned"
                elif deadline_date is not None and today > deadline_date:
                    status = "missed"
                else:
                    status = "in_progress" if progress > 0 else "not_started"
                conn.execute(
                    """
                    UPDATE household_credit_cards
                    SET welcome_progress_amount = %s, welcome_status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    [progress, status, card_id],
                )
                updated += 1
            conn.commit()
        return updated

    # -- alert producers -----------------------------------------------------

    def _pace_alerts(self, cards: list[dict[str, Any]]) -> list[SpendAlert]:
        mtd = self._month_to_date_spend()
        cap = self._monthly_cap(cards)
        period = datetime.now(UTC).strftime("%Y-%m")
        alerts: list[SpendAlert] = []
        if mtd >= cap:
            alerts.append(
                SpendAlert(
                    kind="spend_over_cap",
                    severity="critical",
                    title="Card spend over the monthly cap",
                    body=(
                        f"Month-to-date card spend is ${mtd:,.0f} — over the ${cap:,.0f} cap "
                        "(soft + pending + posted all counted)."
                    ),
                    marker_key=f"spend_over_cap:{period}",
                )
            )
        elif mtd >= cap * WARN_THRESHOLD_PCT:
            alerts.append(
                SpendAlert(
                    kind="spend_pace_hot",
                    severity="warning",
                    title="Card spend running hot",
                    body=(
                        f"Month-to-date card spend is ${mtd:,.0f} — "
                        f"{mtd / cap:.0%} of the ${cap:,.0f} monthly cap."
                    ),
                    marker_key=f"spend_pace_hot:{period}",
                )
            )
        return alerts

    def _welcome_alerts(self, cards: list[dict[str, Any]]) -> list[SpendAlert]:
        alerts: list[SpendAlert] = []
        today = datetime.now(UTC).date()
        for card in cards:
            min_spend = float(card.get("welcome_min_spend") or 0.0)
            deadline = card.get("welcome_deadline")
            opened = card.get("opened_date")
            if (
                card.get("status") != "active"
                or min_spend <= 0
                or card.get("welcome_status") not in {"not_started", "in_progress"}
                or not isinstance(deadline, date)
                or not isinstance(opened, date)
                or deadline <= opened
            ):
                continue
            progress = float(card.get("welcome_progress_amount") or 0.0)
            total_days = (deadline - opened).days
            elapsed = max((today - opened).days, 1)
            projected = progress / elapsed * total_days
            days_left = (deadline - today).days
            if days_left < 0:
                continue  # missed is handled by status, not a push
            if projected < min_spend:
                remaining = min_spend - progress
                alerts.append(
                    SpendAlert(
                        kind="welcome_deadline_risk",
                        severity="warning" if days_left > 14 else "critical",
                        title=f"Welcome bonus at risk: {card['product_name']}",
                        body=(
                            f"${progress:,.0f} of ${min_spend:,.0f} minimum spend with {days_left} days "
                            f"left — ${remaining:,.0f} to go. At the current pace the bonus is missed; "
                            "route household spend to this card."
                        ),
                        marker_key=f"welcome_risk:{card['id']}:{deadline.isoformat()}:{'late' if days_left <= 14 else 'early'}",
                    )
                )
        return alerts

    def _rotation_alerts(self, cards: list[dict[str, Any]]) -> list[SpendAlert]:
        alerts: list[SpendAlert] = []
        today = datetime.now(UTC).date()
        for card in cards:
            opened = card.get("opened_date")
            if (
                not card.get("is_primary_active")
                or card.get("role") != "rotating"
                or not isinstance(opened, date)
            ):
                continue
            held_days = (today - opened).days
            welcome_done = card.get("welcome_status") in {"earned", "missed"}
            if held_days >= ROTATION_DUE_DAYS and welcome_done:
                alerts.append(
                    SpendAlert(
                        kind="rotation_due",
                        severity="info",
                        title="Card rotation due",
                        body=(
                            f"{card['product_name']} has been the active card for {held_days} days and "
                            "its welcome bonus is settled. Check the Cards tab rotation plan for the "
                            "next open (alternate players to stay under Chase 5/24)."
                        ),
                        marker_key=f"rotation_due:{card['id']}:{opened.isoformat()}",
                    )
                )
        return alerts

    def _annual_fee_alerts(self, cards: list[dict[str, Any]]) -> list[SpendAlert]:
        alerts: list[SpendAlert] = []
        today = datetime.now(UTC).date()
        for card in cards:
            due = card.get("annual_fee_due_date")
            if card.get("status") != "active" or not isinstance(due, date):
                continue
            days = (due - today).days
            if 0 <= days <= ANNUAL_FEE_LOOKAHEAD_DAYS:
                fee = float(card.get("annual_fee") or 0.0)
                alerts.append(
                    SpendAlert(
                        kind="annual_fee_renewal",
                        severity="warning",
                        title=f"Annual fee due in {days} days: {card['product_name']}",
                        body=(
                            f"${fee:,.0f} annual fee posts around {due.isoformat()}. If the card no "
                            "longer earns its fee, product-change (downgrade) to a no-fee card instead "
                            "of cancelling — it preserves credit history and the credit line. Never "
                            "cancel within the first year."
                        ),
                        marker_key=f"annual_fee:{card['id']}:{due.isoformat()}",
                    )
                )
        return alerts

    def _catalog_alerts(self, changes: list[dict[str, Any]]) -> list[SpendAlert]:
        alerts: list[SpendAlert] = []
        for change in changes:
            headline = str(change.get("headline") or "").strip()
            if not headline:
                continue
            severity = "warning" if change.get("severity") == "act" else "info"
            detail = str(change.get("detail") or "")
            alerts.append(
                SpendAlert(
                    kind="catalog_change",
                    severity=severity,
                    title=f"Card market change: {headline}",
                    body=detail or headline,
                    marker_key=f"catalog:{abs(hash((headline, detail))) % 10**10}",
                )
            )
        return alerts

    # -- data access ---------------------------------------------------------

    def _owned_cards(self) -> list[dict[str, Any]]:
        with self._storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.status, c.is_primary_active, c.player, c.role,
                       c.opened_date, c.annual_fee_due_date, c.welcome_progress_amount,
                       c.welcome_deadline, c.welcome_status,
                       p.product_name, p.annual_fee, p.welcome_min_spend
                FROM household_credit_cards c
                JOIN credit_card_products p ON p.id = c.product_id
                """,
            ).fetchall()
        keys = (
            "id", "status", "is_primary_active", "player", "role", "opened_date",
            "annual_fee_due_date", "welcome_progress_amount", "welcome_deadline",
            "welcome_status", "product_name", "annual_fee", "welcome_min_spend",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def _month_to_date_spend(self) -> float:
        with self._storage.connection() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM household_transactions
                WHERE flow_type = 'expense' AND removed = FALSE
                  AND transaction_date >= date_trunc('month', CURRENT_DATE)
                """,
            ).fetchone()
        return float((row[0] if row else 0) or 0.0)

    def _monthly_cap(self, cards: list[dict[str, Any]]) -> float:
        """Per-card cap fact for the primary active card, else the default fact,
        else $6.5k (plan §7 budget-fact pattern)."""
        primary = next((c for c in cards if c.get("is_primary_active")), None)
        keys = ["card_monthly_cap_default"]
        if primary:
            keys.insert(0, f"card_monthly_cap:{primary['id']}")
        with self._storage.connection() as conn:
            for key in keys:
                row = conn.execute(
                    "SELECT fact_value FROM household_confirmed_facts WHERE fact_key = %s",
                    [key],
                ).fetchone()
                if row and row[0]:
                    try:
                        return float(row[0])
                    except ValueError:
                        continue
        return DEFAULT_MONTHLY_CAP

    def _already_sent(self, marker_key: str) -> bool:
        with self._storage.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM household_confirmed_facts WHERE fact_key = %s",
                [f"{_MARKER_PREFIX}:{marker_key}"],
            ).fetchone()
        return row is not None

    def _mark_sent(self, marker_key: str) -> None:
        with self._storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO household_confirmed_facts (fact_key, fact_value, confirmed_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (fact_key) DO UPDATE
                SET fact_value = EXCLUDED.fact_value, confirmed_at = EXCLUDED.confirmed_at
                """,
                [f"{_MARKER_PREFIX}:{marker_key}", datetime.now(UTC).isoformat()],
            )
            conn.commit()


def evaluate_and_dispatch(
    *, trigger: str, catalog_changes: list[dict[str, Any]] | None = None
) -> list[SpendAlert]:
    """Module-level convenience for workflow/endpoint call sites."""
    return SpendAlertService().evaluate_and_dispatch(
        trigger=trigger, catalog_changes=catalog_changes
    )
