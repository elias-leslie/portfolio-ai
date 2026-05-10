"""Source-specific builders for the home action queue."""

from __future__ import annotations

from collections.abc import Iterable

from app.api.portfolio.analytics_routes import get_analytics_payload
from app.api.recommendations.logic import DEFAULT_POSITION_PCT
from app.api.recommendations.queries import fetch_recommendations
from app.api.strategy_lab.service import (
    _eligible_accounts as _strategy_lab_eligible_accounts,
)
from app.api.strategy_lab.service import (
    _eligible_positions as _strategy_lab_eligible_positions,
)
from app.api.strategy_lab.service import (
    _held_positions_by_symbol as _strategy_lab_held_by_symbol,
)
from app.api.strategy_lab.service import (
    _watchlist_membership as _strategy_lab_watchlist_membership,
)
from app.api.symbols.builders import build_portfolio_section
from app.api.symbols.data_fetchers import get_portfolio_data
from app.api.symbols.decisions import build_symbol_decision
from app.logging_config import get_logger
from app.services._home_action_ranking import (
    action_rank_score,
    household_rank_score,
    numeric_value,
    position_impact_score,
)
from app.services.household_portfolio_totals import get_effective_portfolio_totals

logger = get_logger(__name__)


def _field_value(container: object, key: str, default: object = None) -> object:
    if isinstance(container, dict):
        return container.get(key, default)
    return getattr(container, key, default)


def _title_with_symbol(symbol: str | None, headline: str) -> str:
    if not symbol:
        return headline
    return f"{symbol}: {headline}"


def _portfolio_position_for_symbol(storage: object | None, symbol: str | None):
    if not storage or not symbol:
        return None

    try:
        portfolio = get_portfolio_data(symbol, storage)
        return build_portfolio_section(
            portfolio.get("position"),
            portfolio.get("summary"),
        ).position
    except Exception as exc:
        logger.warning("home_action_position_context_failed", symbol=symbol, error=str(exc))
        return None


def _is_household_jenny_decision(decision: dict[str, object]) -> bool:
    action = str(decision.get("action", "") or "")
    source_kind = str(decision.get("source_kind", "") or "")
    return action.startswith("household_inbox:") or source_kind == "jenny_alert_household"


def _household_action_label(item: object) -> str:
    action_href = str(getattr(item, "action_href", "") or "")
    need_id = str(getattr(item, "id", "") or "")
    need_type = str(getattr(item, "need_type", "") or "")
    action_label = str(getattr(item, "action_label", "") or "")

    label = action_label or "Resolve"
    if "focus=account-coverage" in action_href or "focus=discovered-accounts" in action_href:
        label = "Review accounts"
    elif "utility=evidence" in action_href:
        label = action_label or "Add evidence"
    elif "utility=planning" in action_href:
        section = need_id.removeprefix("need_planning_").replace("_", " ")
        label = (
            f"Add {section} info"
            if section and section != need_id
            else "Add planning info"
        )
    elif getattr(item, "related_question_id", None):
        label = "Answer question"
    elif need_type == "confirm":
        label = "Confirm"
    return label


def build_portfolio_health_actions() -> list[dict[str, object]]:
    try:
        analytics = get_analytics_payload(include_paper=False)
    except Exception as exc:
        logger.warning("home_action_portfolio_health_failed", error=str(exc))
        return []

    if analytics.num_positions == 0:
        return []

    concentration = analytics.concentration
    top_holding_pct = float(_field_value(concentration, "top_holding_pct", 0.0) or 0.0)
    top_3_pct = float(_field_value(concentration, "top_3_pct", 0.0) or 0.0)
    concentration_method = str(_field_value(concentration, "method", "line_item") or "line_item")
    top_holding_name = str(_field_value(concentration, "top_holding_name", "") or "").strip()
    vehicle_top_holding_pct = float(
        _field_value(concentration, "vehicle_top_holding_pct", top_holding_pct)
        or top_holding_pct
    )
    vehicle_top_holding_name = str(
        _field_value(concentration, "vehicle_top_holding_name", "") or ""
    ).strip()
    diversification_score = (
        _field_value(analytics.diversification_score, "score")
        if analytics.diversification_score is not None
        else None
    )

    if top_holding_pct >= 35:
        priority = "high" if top_holding_pct >= 50 else "warning"
        return [
            {
                "id": "portfolio-health-top-holding",
                "source": "portfolio",
                "category": "investing",
                "priority": priority,
                "title": "Portfolio needs a concentration check",
                "detail": (
                    (
                        f"Top single-name exposure {top_holding_name or 'is'} is "
                        f"{top_holding_pct:.1f}% after ETF look-through. Largest "
                        f"vehicle {vehicle_top_holding_name or 'position'} is "
                        f"{vehicle_top_holding_pct:.1f}%. "
                    )
                    if concentration_method == "lookthrough"
                    else f"Largest holding is {top_holding_pct:.1f}% of the positioned portfolio. "
                )
                + "Open Holdings to review portfolio concentration.",
                "action_label": "Check concentration",
                "href": "/portfolio?tab=holdings&highlight=concentration#portfolio-overview",
                "symbol": None,
                "badge": "Concentration",
                "_rank_score": action_rank_score(
                    priority,
                    impact=min(top_holding_pct * 5, 600.0),
                    confidence=80.0,
                    effort=20.0,
                ),
            }
        ]

    if top_3_pct >= 70 or (diversification_score is not None and diversification_score < 50):
        diversification_gap = (
            max(0.0, 50.0 - float(diversification_score))
            if diversification_score is not None
            else 0.0
        )
        diversification_detail = (
            f"Diversification score is {diversification_score:.0f}."
            if diversification_score is not None
            else "Diversification scoring is still limited."
        )
        return [
            {
                "id": "portfolio-health-diversification",
                "source": "portfolio",
                "category": "investing",
                "priority": "warning",
                "title": "Portfolio spread needs a review",
                "detail": (
                    (
                        f"Top three single-name exposures are {top_3_pct:.1f}% after ETF look-through. "
                        if concentration_method == "lookthrough"
                        else f"Top three holdings are {top_3_pct:.1f}% of invested assets. "
                    )
                    + diversification_detail
                ),
                "action_label": "Review holdings",
                "href": "/portfolio?tab=holdings&highlight=concentration#portfolio-overview",
                "symbol": None,
                "badge": "Portfolio",
                "_rank_score": action_rank_score(
                    "warning",
                    impact=min(top_3_pct * 3 + diversification_gap * 6, 450.0),
                    confidence=60.0 if diversification_score is not None else 20.0,
                    effort=30.0,
                ),
            }
        ]

    return []


def _strategy_lab_universe() -> set[str]:
    """Symbols Strategy Lab can render (watchlist + held).

    Used to route Today actions into Strategy Lab when there's full account
    context, and to /symbols otherwise. No new tables — both pieces are just
    references to existing watchlist + portfolio state.
    """
    try:
        accounts = _strategy_lab_eligible_accounts()
        positions = _strategy_lab_eligible_positions(accounts)
        held = set(_strategy_lab_held_by_symbol(positions).keys())
        watchlist = set(_strategy_lab_watchlist_membership().keys())
        return {s.upper() for s in watchlist} | {s.upper() for s in held}
    except Exception as exc:
        logger.warning("home_action_strategy_lab_universe_failed", error=str(exc))
        return set()


def build_recommendation_actions(storage: object) -> list[dict[str, object]]:
    try:
        portfolio_size = get_effective_portfolio_totals(
            storage,
            include_paper=False,
        ).effective_invested_total_value
        recommendations = fetch_recommendations(
            min_strength=6,
            limit=3,
            signal_type="BUY",
            portfolio_size=portfolio_size,
            position_pct=DEFAULT_POSITION_PCT,
            validation_filter=None,
        )
    except Exception as exc:
        logger.warning("home_action_recommendations_failed", error=str(exc))
        return []

    strategy_lab_universe = _strategy_lab_universe()
    actions: list[dict[str, object]] = []
    for recommendation in recommendations:
        symbol_key = recommendation.symbol.upper()
        in_strategy_lab = symbol_key in strategy_lab_universe
        decision = build_symbol_decision(
            symbol=recommendation.symbol,
            recommendation={
                "action": "INITIATE_POSITION",
                "reasoning": [f"Strong BUY signal ({recommendation.signal_strength}/10)"],
            },
            generated_at=recommendation.generated_at or recommendation.signal_date,
        ).model_dump(mode="json")
        confidence_badge = "High" if recommendation.validation_type == "both" else "Medium"
        href = (
            f"/strategy-lab?symbol={recommendation.symbol}"
            if in_strategy_lab
            else f"/symbols/{recommendation.symbol}?tab=decision"
        )
        action_label = "Open Strategy Lab" if in_strategy_lab else "Open decision"
        detail_suffix = (
            " Strategy Lab has the account-aware ticket."
            if in_strategy_lab
            else ""
        )
        actions.append(
            {
                "id": f"recommendation-{recommendation.symbol}-{recommendation.strategy_id}",
                "source": "recommendations",
                "category": "investing",
                "priority": "high",
                "title": _title_with_symbol(recommendation.symbol, decision["headline"]),
                "detail": (
                    f"{decision['summary']} "
                    f"Suggested size ${recommendation.position_size_dollars:,.0f}."
                    f"{detail_suffix}"
                ),
                "action_label": action_label,
                "href": href,
                "symbol": recommendation.symbol,
                "badge": confidence_badge,
                "decision": decision,
                "execution": {
                    "kind": "workflow_transition",
                    "symbol": recommendation.symbol,
                    "stage": "tracked" if in_strategy_lab else "thesis_ready",
                },
                "_rank_score": action_rank_score(
                    "high",
                    impact=min(
                        numeric_value(recommendation.position_size_dollars) / 1000,
                        300.0,
                    ),
                    confidence=120.0 if recommendation.validation_type == "both" else 60.0,
                    effort=80.0,
                ),
            }
        )
    return actions


def build_jenny_actions(dashboard: object, storage: object | None) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for notification in dashboard.notifications[:3]:
        portfolio_position = _portfolio_position_for_symbol(
            storage,
            notification.symbol,
        )
        decision = build_symbol_decision(
            symbol=notification.symbol or "",
            recommendation=None,
            generated_at=notification.created_at,
            notifications=[notification],
            portfolio_position=portfolio_position,
        ).model_dump(mode="json")
        if _is_household_jenny_decision(decision):
            continue
        href = (
            f"/symbols/{notification.symbol}?tab=decision"
            if notification.symbol
            else "/portfolio"
        )
        priority = (
            "critical"
            if notification.severity == "critical"
            else "warning"
            if notification.severity == "warning"
            else "medium"
        )
        actions.append(
            {
                "id": notification.id,
                "source": "jenny",
                "category": "investing",
                "priority": priority,
                "title": _title_with_symbol(notification.symbol, decision["headline"]),
                "detail": decision["summary"],
                "action_label": "Review decision",
                "href": href,
                "symbol": notification.symbol,
                "badge": notification.severity.title(),
                "decision": decision,
                "execution": {
                    "kind": "acknowledge_notification",
                    "notification_id": notification.id,
                },
                "_rank_score": action_rank_score(
                    priority,
                    impact=position_impact_score(portfolio_position),
                    confidence=80.0,
                    effort=30.0,
                ),
            }
        )

    for review in dashboard.trade_reviews[:2]:
        actions.append(
            {
                "id": review.id,
                "source": "jenny",
                "category": "learning",
                "priority": "medium",
                "title": f"Review outcome on {review.symbol}",
                "detail": review.lesson,
                "action_label": "Open symbol",
                "href": f"/symbols/{review.symbol}?tab=decision",
                "symbol": review.symbol,
                "badge": review.outcome_label.title(),
                "_rank_score": action_rank_score(
                    "medium",
                    confidence=40.0,
                    effort=40.0,
                ),
            }
        )

    return actions


def build_jenny_actions_from_service(
    jenny_service: object,
    storage: object | None,
) -> list[dict[str, object]]:
    try:
        dashboard = jenny_service.get_dashboard()
    except Exception as exc:
        logger.warning("home_action_jenny_failed", error=str(exc))
        return []

    return build_jenny_actions(dashboard, storage)


def build_workflow_actions(workflows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for workflow in workflows:
        stage = str(workflow["stage"])
        symbol = str(workflow["symbol"])
        if stage == "review_due":
            actions.append(
                {
                    "id": f"workflow-review-{symbol}",
                    "source": "workflow",
                    "category": "learning",
                    "priority": "medium",
                    "title": f"Close the loop on {symbol}",
                    "detail": "Workflow stage: review due.",
                    "action_label": "Mark reviewed",
                    "href": f"/symbols/{symbol}",
                    "symbol": symbol,
                    "badge": "Review due",
                    "execution": {
                        "kind": "workflow_transition",
                        "symbol": symbol,
                        "stage": "tracked",
                    },
                    "_rank_score": action_rank_score(
                        "medium",
                        freshness=120.0,
                        effort=20.0,
                    ),
                }
            )
        elif stage == "invalidated":
            actions.append(
                {
                    "id": f"workflow-invalidated-{symbol}",
                    "source": "workflow",
                    "category": "investing",
                    "priority": "warning",
                    "title": f"Reset {symbol} after invalidation",
                    "detail": "Workflow stage: invalidated.",
                    "action_label": "Restart discovery",
                    "href": f"/symbols/{symbol}",
                    "symbol": symbol,
                    "badge": "Invalidated",
                    "execution": {
                        "kind": "workflow_transition",
                        "symbol": symbol,
                        "stage": "discover",
                    },
                    "_rank_score": action_rank_score(
                        "warning",
                        freshness=100.0,
                        effort=40.0,
                    ),
                }
            )
    return actions


def build_workflow_actions_from_service(workflow_service: object) -> list[dict[str, object]]:
    try:
        workflows = workflow_service.list_priority_workflows(limit=3)
    except Exception as exc:
        logger.warning("home_action_workflow_failed", error=str(exc))
        return []

    return build_workflow_actions(workflows)


def build_household_actions(items: Iterable[object]) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    for index, item in enumerate(list(items)[:4], start=1):
        actions.append(
            {
                "id": f"household-{index}-{item.id}",
                "source": "household",
                "category": "household",
                "priority": item.priority,
                "title": item.title,
                "detail": item.detail,
                "action_label": _household_action_label(item),
                "href": item.action_href or "/money",
                "symbol": None,
                "badge": "Household",
                "_rank_score": household_rank_score(item),
            }
        )

    return actions


def build_household_actions_from_service(household_service: object) -> list[dict[str, object]]:
    try:
        dashboard = household_service.get_dashboard()
    except Exception as exc:
        logger.warning("home_action_household_failed", error=str(exc))
        return []

    return build_household_actions(dashboard.inbox)
