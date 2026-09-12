"""Source-specific builders for the home action queue."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlencode

from app.api.portfolio.analytics_routes import get_analytics_payload
from app.api.symbols.builders import build_portfolio_section
from app.api.symbols.data_fetchers import get_portfolio_data
from app.api.symbols.decisions import build_symbol_decision
from app.logging_config import get_logger
from app.services._home_action_ranking import (
    action_rank_score,
    household_rank_score,
    position_impact_score,
)

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
        label = f"Add {section} info" if section and section != need_id else "Add planning info"
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
        _field_value(concentration, "vehicle_top_holding_pct", top_holding_pct) or top_holding_pct
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
            f"/symbols/{notification.symbol}?tab=decision" if notification.symbol else "/portfolio"
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
        raise

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
                    "action_label": "Review decision",
                    "href": f"/symbols/{symbol}?tab=track",
                    "symbol": symbol,
                    "badge": "Review due",
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
                    "action_label": "Review next step",
                    "href": f"/symbols/{symbol}?tab=track",
                    "symbol": symbol,
                    "badge": "Invalidated",
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
        raise

    return build_workflow_actions(workflows)


def build_household_actions(
    items: Iterable[object],
    accounts: Iterable[object] = (),
    questions: Iterable[object] = (),
    discovered_accounts: Iterable[object] = (),
) -> list[dict[str, object]]:
    question_map = {str(_field_value(question, "id")): question for question in questions}
    discovered_map = {f"discovered-{_field_value(a, 'key')}": a for a in discovered_accounts}
    account_map = {}
    for account in accounts:
        for key in ("id", "household_account_id", "tracked_account_id"):
            value = _field_value(account, key)
            if value:
                account_map[str(value)] = account
    actions: list[dict[str, object]] = []
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    # Rank all candidates before limiting the queue. The inbox's first four
    # can be older evidence requests, not the four decisions most affected.
    for item in items:
        need_id = str(_field_value(item, "id", ""))
        account = account_map.get(str(_field_value(item, "related_account_id", "")))
        affects = set(_field_value(item, "affects", []) or [])
        priority = str(_field_value(item, "priority", "low"))
        score = household_rank_score(item)
        is_refresh = any(
            need_id.endswith(f"-{code}")
            for code in (
                "stale_balance",
                "stale_evidence",
                "refresh_balance_soon",
                "refresh_soon",
                "refresh_transactions_soon",
                "stale_transactions",
                "missing_transaction_history",
                "statement_gap",
                "missing_evidence",
                "missing_current_state",
            )
        )
        if need_id.startswith("account-control-"):
            score = max(score, action_rank_score("critical", impact=500))
        elif affects.intersection({"safe_to_spend", "monthly_spend", "budget_status"}):
            score = max(score, action_rank_score("high", impact=600))
        elif is_refresh and _field_value(account, "asset_group") == "education":
            priority = "low"
            score = action_rank_score("low", impact=100)
        action = {
            "id": f"household-{need_id}",
            "source": "household",
            "category": "household",
            "priority": priority,
            "title": _field_value(item, "title", "Review household evidence"),
            "detail": _field_value(item, "detail", ""),
            "action_label": _household_action_label(item),
            "href": _field_value(item, "action_href") or "/money",
            "symbol": None,
            "badge": "Household",
            "_rank_score": score,
        }
        question_id = _field_value(item, "related_question_id")
        canonical_id = _field_value(account, "household_account_id")
        discovered = discovered_map.get(need_id)
        if canonical_id:
            action["account"] = {
                "kind": "registered", "id": str(canonical_id),
                "label": str(_field_value(account, "label", "Account")),
                "account_type": str(_field_value(account, "account_type", "other")),
            }
        elif discovered:
            action["account"] = {
                "kind": "discovered", "id": str(_field_value(discovered, "key")),
                "label": str(_field_value(discovered, "suggested_label")),
                "account_type": str(_field_value(discovered, "account_type", "other")),
            }
        if question_id:
            question = question_map.get(str(question_id), item)
            action["question"] = {
                "id": str(question_id),
                "format": _field_value(question, "question_format") or "short_text",
                "options": _field_value(question, "options") or [],
            }
        institution = str(_field_value(account, "institution_name", "") or "").strip()
        if is_refresh and institution:
            kind = (
                "transactions"
                if any(
                    word in need_id
                    for word in ("transactions", "transaction_history", "statement_gap")
                )
                else "balances"
            )
            groups.setdefault((institution, kind), []).append(action)
        else:
            actions.append(action)
    for (institution, kind), group in groups.items():
        group.sort(key=lambda action: float(action["_rank_score"]), reverse=True)
        if len(group) == 1:
            actions.extend(group)
            continue
        lead = group[0]
        actions.append(
            {
                **lead,
                "id": f"household-refresh-{institution}-{kind}",
                "title": f"Update {institution} {kind} for {len(group)} accounts",
                "detail": "One provider review can address these requests: "
                + "; ".join(str(action["title"]) for action in group)
                + ".",
                "href": "/money?" + urlencode({"tab": "accounts", "institution": institution}),
                "action_label": "Review these accounts",
                "account": None,  # A grouped request must not close only its lead account.
            }
        )
    return sorted(actions, key=lambda action: float(action["_rank_score"]), reverse=True)


def build_household_actions_from_service(household_service: object) -> list[dict[str, object]]:
    try:
        dashboard = household_service.get_dashboard()
    except Exception as exc:
        logger.warning("home_action_household_failed", error=str(exc))
        raise

    return build_household_actions(
        dashboard.inbox, getattr(dashboard, "accounts", []), getattr(dashboard, "questions", []),
        getattr(dashboard, "discovered_accounts", []),
    )
