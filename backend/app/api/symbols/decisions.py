"""Shared symbol decision resolution helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.jenny import JennyNotification, JennySymbolReview

from .models import DecisionSection, PositionInfo


def _format_label(value: str | None, fallback: str = "Awaiting review") -> str:
    if not value:
        return fallback
    words = value.replace("_", " ").lower()
    return words[:1].upper() + words[1:]


def _strip_symbol_prefix(title: str, symbol: str) -> str:
    prefix = f"{symbol.upper()}: "
    if title.upper().startswith(prefix.upper()):
        return title[len(prefix):]
    return title


def _dedupe_reasoning(reasons: list[str | None]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for reason in reasons:
        normalized = (reason or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _format_position_fact(symbol: str, position: PositionInfo | None) -> str | None:
    if position is None:
        return None

    if position.gain_pct is None and position.weight_pct is None:
        return (
            f"Current live position: {symbol.upper()} is held, but live price and "
            "invested weight are unavailable."
        )

    if position.gain_pct is None:
        performance = "held with unavailable live gain/loss"
    elif abs(position.gain_pct) < 0.05:
        performance = "about flat from cost basis"
    else:
        direction = "up" if position.gain_pct >= 0 else "down"
        performance = f"{direction} {abs(position.gain_pct):.1f}% from cost basis"

    if position.weight_pct is None:
        return (
            f"Current live position: {symbol.upper()} is {performance}; invested "
            "weight is unavailable."
        )

    return (
        f"Current live position: {symbol.upper()} is {performance} and now makes up "
        f"{position.weight_pct:.1f}% of invested assets."
    )


def _is_stored_position_fact(reason: str | None) -> bool:
    if not reason or "%" not in reason:
        return False

    normalized = reason.lower()
    return any(
        marker in normalized
        for marker in ("portfolio", "cost basis", "current gain", "makes up")
    )


def _sort_notifications(notifications: list[JennyNotification]) -> list[JennyNotification]:
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    return sorted(
        notifications,
        key=lambda notification: (
            severity_rank.get(notification.severity, 99),
            notification.created_at,
        ),
        reverse=False,
    )


def _normalize_timestamp(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def build_symbol_decision(
    *,
    symbol: str,
    recommendation: dict[str, Any] | None,
    generated_at: datetime | str | None,
    notifications: list[JennyNotification] | None = None,
    latest_review: JennySymbolReview | None = None,
    portfolio_position: PositionInfo | None = None,
) -> DecisionSection:
    """Resolve the current decision for a symbol from Jenny + live model context."""
    active_notification = _sort_notifications(notifications or [])[:1]
    if active_notification:
        notification = active_notification[0]
        current_position_fact = _format_position_fact(symbol, portfolio_position)
        stored_detail = (
            None
            if current_position_fact and _is_stored_position_fact(notification.detail)
            else notification.detail
        )
        reasoning = _dedupe_reasoning(
            [current_position_fact, stored_detail, notification.recommendation]
        )
        return DecisionSection(
            action=notification.category,
            headline=_strip_symbol_prefix(notification.title, symbol),
            summary=notification.recommendation
            or notification.detail
            or "Jenny raised an active alert for this symbol.",
            reasoning=reasoning,
            source_kind="jenny_alert",
            source_label="Jenny alert",
            source_timestamp=notification.created_at,
            severity=notification.severity,
        )

    if latest_review is not None:
        action = latest_review.management_action or latest_review.final_verdict or "review"
        reasoning = _dedupe_reasoning([latest_review.management_detail, *latest_review.reasons])
        return DecisionSection(
            action=action,
            headline=_format_label(action, "Review"),
            summary=reasoning[0]
            if reasoning
            else "Jenny has a recent review but no short summary is available yet.",
            reasoning=reasoning,
            source_kind="jenny_review",
            source_label="Jenny review",
            source_timestamp=_normalize_timestamp(
                latest_review.evaluations[0].created_at if latest_review.evaluations else None
            ),
        )

    recommendation = recommendation or {}
    reasoning = [
        str(reason)
        for reason in recommendation.get("reasoning", [])
        if isinstance(reason, str) and reason.strip()
    ]
    action = str(recommendation.get("action") or "awaiting_review")
    return DecisionSection(
        action=action,
        headline=_format_label(action, "—"),
        summary=reasoning[0] if reasoning else "No live recommendation summary is available yet.",
        reasoning=reasoning,
        source_kind="live_signal_model",
        source_label="Live signal model",
        source_timestamp=_normalize_timestamp(generated_at),
    )
