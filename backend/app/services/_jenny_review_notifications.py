"""Notification upsert and extraction helpers for Jenny reviews."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

MANAGED_NOTIFICATION_CATEGORIES = frozenset(
    {
        "missing_thesis",
        "thesis_invalidation",
        "watchlist_buy_candidate",
    }
)


def extract_symbol_profile(evaluations: list[dict[str, Any]]) -> dict[str, Any]:
    for evaluation in evaluations:
        profile = (evaluation.get("metadata") or {}).get("symbol_profile")
        if isinstance(profile, dict):
            return profile
    return {}


def extract_invalidation_triggers(evaluations: list[dict[str, Any]]) -> list[str]:
    for evaluation in evaluations:
        raw_triggers = (evaluation.get("metadata") or {}).get("invalidation_triggers")
        if isinstance(raw_triggers, list):
            return [str(trigger) for trigger in raw_triggers if trigger]
    return []


def _find_existing_notification(conn: Any, category: str, symbol: str | None) -> Any:
    """Find the most recent open notification for a category/symbol pair."""
    return conn.execute(
        """
        SELECT id
        FROM jenny_notifications
        WHERE status = 'open'
          AND category = %s
          AND COALESCE(symbol, '') = COALESCE(%s, '')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [category, symbol],
    ).fetchone()


def _execute_update(
    conn: Any,
    notification_id: str,
    routine_id: str,
    severity: str,
    title: str,
    detail: str,
    recommendation: str | None,
) -> None:
    """Update an existing notification."""
    conn.execute(
        """
        UPDATE jenny_notifications
        SET routine_id = %s,
            severity = %s,
            title = %s,
            detail = %s,
            recommendation = %s,
            created_at = %s
        WHERE id = %s
        """,
        [
            routine_id,
            severity,
            title,
            detail,
            recommendation,
            datetime.now(UTC).isoformat(),
            notification_id,
        ],
    )


def _execute_insert(
    conn: Any,
    routine_id: str,
    symbol: str | None,
    category: str,
    severity: str,
    title: str,
    detail: str,
    recommendation: str | None,
) -> None:
    """Insert a new notification."""
    conn.execute(
        """
        INSERT INTO jenny_notifications (
            id, routine_id, symbol, category, severity, status, title, detail, recommendation, created_at
        ) VALUES (%s, %s, %s, %s, %s, 'open', %s, %s, %s, %s)
        """,
        [
            str(uuid.uuid4()),
            routine_id,
            symbol,
            category,
            severity,
            title,
            detail,
            recommendation,
            datetime.now(UTC).isoformat(),
        ],
    )


def upsert_notification(
    service: Any,
    routine_id: str,
    symbol: str | None,
    *,
    category: str,
    severity: str,
    title: str,
    detail: str,
    recommendation: str | None,
) -> None:
    """Upsert a notification (update existing or insert new)."""
    with service.storage.connection() as conn:
        existing = _find_existing_notification(conn, category, symbol)

        if existing:
            _execute_update(
                conn,
                str(existing[0]),
                routine_id,
                severity,
                title,
                detail,
                recommendation,
            )
        else:
            _execute_insert(
                conn,
                routine_id,
                symbol,
                category,
                severity,
                title,
                detail,
                recommendation,
            )
        conn.commit()


def create_notifications(
    service: Any,
    *,
    routine_id: str,
    live_symbols: set[str],
    evaluations_by_symbol: dict[str, list[dict[str, Any]]],
) -> int:
    count = 0
    review_map = {
        symbol: service._aggregate_symbol_review(
            symbol, evaluations, service.thesis_service.get_thesis(symbol)
        )
        for symbol, evaluations in evaluations_by_symbol.items()
    }
    position_actions = service._build_position_action_map(
        {symbol: review for symbol, review in review_map.items() if symbol in live_symbols}
    )

    for symbol, review in review_map.items():
        position_action = position_actions.get(symbol)
        evaluations = evaluations_by_symbol.get(symbol, [])
        active_categories: set[str] = set()

        count += _emit_position_notification(
            service,
            routine_id,
            symbol,
            live_symbols,
            review,
            position_action,
            evaluations,
            active_categories,
        )
        count += _emit_watchlist_notification(
            service,
            routine_id,
            symbol,
            live_symbols,
            review,
            active_categories,
        )
        count += _emit_invalidation_notification(
            service,
            routine_id,
            symbol,
            live_symbols,
            evaluations,
            position_action,
            active_categories,
        )
        count += _emit_missing_thesis_notification(
            service,
            routine_id,
            symbol,
            evaluations,
            active_categories,
        )
        resolve_superseded_notifications(service, symbol, active_categories=active_categories)

    return count


def is_managed_notification_category(category: str) -> bool:
    return category.startswith("position_") or category in MANAGED_NOTIFICATION_CATEGORIES


def resolve_superseded_notifications(
    service: Any,
    symbol: str | None,
    *,
    active_categories: set[str],
) -> None:
    """Resolve managed notifications for a symbol that no longer apply."""
    with service.storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT id, category
            FROM jenny_notifications
            WHERE status = 'open'
              AND COALESCE(symbol, '') = COALESCE(%s, '')
            """,
            [symbol],
        ).fetchall()

        stale_notification_ids = [
            str(notification_id)
            for notification_id, category in rows
            if is_managed_notification_category(str(category or ""))
            and str(category or "") not in active_categories
        ]

        for notification_id in stale_notification_ids:
            conn.execute(
                """
                UPDATE jenny_notifications
                SET status = %s
                WHERE id = %s
                """,
                ["resolved", notification_id],
            )
        conn.commit()


def _emit_position_notification(
    service: Any,
    routine_id: str,
    symbol: str,
    live_symbols: set[str],
    review: Any,
    position_action: dict[str, Any] | None,
    evaluations: list[dict[str, Any]],
    active_categories: set[str],
) -> int:
    if symbol not in live_symbols:
        return 0
    if position_action and position_action["action"] != "hold":
        active_categories.add(f"position_{position_action['action']}")
        service._upsert_notification(
            routine_id,
            symbol,
            category=f"position_{position_action['action']}",
            severity=position_action["severity"],
            title=position_action["title"],
            detail=position_action["detail"],
            recommendation=position_action["recommendation"],
        )
        return 1
    if review.final_verdict in {"exit", "trim", "review"}:
        active_categories.add(f"position_{review.final_verdict}")
        service._upsert_notification(
            routine_id,
            symbol,
            category=f"position_{review.final_verdict}",
            severity="critical" if review.final_verdict == "exit" else "warning",
            title=f"{symbol}: {review.final_verdict.title()} this position",
            detail=" ".join(review.reasons) or f"Jenny wants you to {review.final_verdict} {symbol}.",
            recommendation=review.evaluations[0].recommendation if review.evaluations else None,
        )
        return 1
    return 0


def _emit_watchlist_notification(
    service: Any,
    routine_id: str,
    symbol: str,
    live_symbols: set[str],
    review: Any,
    active_categories: set[str],
) -> int:
    if symbol in live_symbols:
        return 0
    if review.final_verdict != "buy" or (review.average_confidence or 0) < 0.7:
        return 0
    active_categories.add("watchlist_buy_candidate")
    service._upsert_notification(
        routine_id,
        symbol,
        category="watchlist_buy_candidate",
        severity="info",
        title=f"{symbol}: high-conviction setup",
        detail=" ".join(review.reasons) or f"Jenny flagged {symbol} as a vetted setup.",
        recommendation=review.evaluations[0].recommendation if review.evaluations else None,
    )
    return 1


def _emit_invalidation_notification(
    service: Any,
    routine_id: str,
    symbol: str,
    live_symbols: set[str],
    evaluations: list[dict[str, Any]],
    position_action: dict[str, Any] | None,
    active_categories: set[str],
) -> int:
    invalidation_triggers = extract_invalidation_triggers(evaluations)
    if not invalidation_triggers:
        return 0
    if position_action and position_action["action"] == "exit":
        return 0
    active_categories.add("thesis_invalidation")
    service._upsert_notification(
        routine_id,
        symbol,
        category="thesis_invalidation",
        severity="critical" if symbol in live_symbols else "warning",
        title=f"{symbol}: thesis invalidation triggered",
        detail=" ".join(invalidation_triggers),
        recommendation="Review the thesis and current price action before holding or adding.",
    )
    return 1


def _emit_missing_thesis_notification(
    service: Any,
    routine_id: str,
    symbol: str,
    evaluations: list[dict[str, Any]],
    active_categories: set[str],
) -> int:
    thesis = service.thesis_service.get_thesis(symbol)
    if thesis is not None:
        return 0
    profile = extract_symbol_profile(evaluations)
    if profile.get("is_passive_fund"):
        return 0
    active_categories.add("missing_thesis")
    service._upsert_notification(
        routine_id,
        symbol,
        category="missing_thesis",
        severity="warning",
        title=f"{symbol}: thesis missing",
        detail="Jenny could not find an active thesis for this symbol yet.",
        recommendation="Review the symbol and let Jenny regenerate the thesis before acting.",
    )
    return 1
