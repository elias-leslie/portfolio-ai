"""Aggregate prioritized product actions for the home page."""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.portfolio.analytics_routes import get_analytics_payload
from app.api.recommendations.logic import DEFAULT_POSITION_PCT
from app.api.recommendations.queries import fetch_recommendations
from app.api.symbols.builders import build_portfolio_section
from app.api.symbols.data_fetchers import get_portfolio_data
from app.api.symbols.decisions import build_symbol_decision
from app.logging_config import get_logger
from app.services._home_action_ranking import (
    PRIORITY_RANK,
    action_rank_score,
    household_rank_score,
    internal_rank_score,
    numeric_value,
    position_impact_score,
    public_action,
)
from app.services.household_finance_service import HouseholdFinanceService
from app.services.household_portfolio_totals import get_effective_portfolio_totals
from app.services.jenny_operator_service import JennyOperatorService
from app.services.symbol_workflow_service import SymbolWorkflowService
from app.storage import get_storage

logger = get_logger(__name__)


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


def _normalized_action_title(action: dict[str, object]) -> str:
    return " ".join(str(action.get("title", "") or "").lower().split())


def _action_specificity_score(action: dict[str, object]) -> float:
    source = str(action.get("source", "") or "")
    href = str(action.get("href", "") or "")
    detail = str(action.get("detail", "") or "")

    score = {
        "household": 40.0,
        "portfolio": 30.0,
        "recommendations": 25.0,
        "workflow": 20.0,
        "jenny": 10.0,
    }.get(source, 0.0)

    if href.startswith("/money?"):
        score += 12.0
    elif href.startswith("/portfolio?"):
        score += 10.0
    elif href.startswith("/symbols/"):
        score += 8.0
    elif href.startswith("/money"):
        score += 6.0

    if detail:
        score += min(len(detail) / 80.0, 3.0)

    if action.get("execution"):
        score -= 2.0

    return score


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


class HomeActionService:
    """Build a ranked cross-product action queue for the home dashboard."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.household_service: HouseholdFinanceService | None = None
        self.jenny_service: JennyOperatorService | None = None
        self.workflow_service: SymbolWorkflowService | None = None

    def _household_service(self) -> HouseholdFinanceService:
        service = getattr(self, "household_service", None)
        if service is None:
            service = HouseholdFinanceService()
            self.household_service = service
        return service

    def _jenny_service(self) -> JennyOperatorService:
        service = getattr(self, "jenny_service", None)
        if service is None:
            service = JennyOperatorService()
            self.jenny_service = service
        return service

    def _workflow_service(self) -> SymbolWorkflowService:
        service = getattr(self, "workflow_service", None)
        if service is None:
            service = SymbolWorkflowService()
            self.workflow_service = service
        return service

    def get_action_queue(self) -> dict[str, object]:
        actions: list[dict[str, object]] = []
        actions.extend(self._recommendation_actions())
        actions.extend(self._portfolio_health_actions())
        actions.extend(self._jenny_actions())
        actions.extend(self._workflow_actions())
        actions.extend(self._household_actions())

        if not actions:
            actions.append(
                {
                    "id": "calm-default",
                    "source": "system",
                    "category": "overview",
                    "priority": "low",
                    "title": "No urgent actions",
                    "detail": "The app does not see any high-priority investing or household follow-ups right now.",
                    "action_label": "Open dashboard",
                    "href": "/",
                    "symbol": None,
                    "badge": "Calm",
                }
            )

        deduped_by_key: dict[tuple[str, str | None], dict[str, object]] = {}
        for action in actions:
            key = (
                _normalized_action_title(action),
                str(action.get("symbol") or "").upper() or None,
            )
            existing = deduped_by_key.get(key)
            if existing is None:
                deduped_by_key[key] = action
                continue

            existing_score = (
                _action_specificity_score(existing),
                internal_rank_score(existing),
            )
            candidate_score = (
                _action_specificity_score(action),
                internal_rank_score(action),
            )
            if candidate_score > existing_score:
                deduped_by_key[key] = action

        deduped = list(deduped_by_key.values())

        deduped.sort(
            key=lambda action: (
                -internal_rank_score(action),
                PRIORITY_RANK.get(str(action.get("priority", "low")), 99),
                str(action.get("title", "")),
            )
        )
        queue = [public_action(action) for action in deduped[:8]]
        summary = (
            "Nothing urgent is queued."
            if not queue
            else f"{len(queue)} prioritized action{'s' if len(queue) != 1 else ''} ready."
        )
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "actions": queue,
            "summary": summary,
        }

    def _portfolio_health_actions(self) -> list[dict[str, object]]:
        try:
            analytics = get_analytics_payload(include_paper=False)
        except Exception as exc:
            logger.warning("home_action_portfolio_health_failed", error=str(exc))
            return []

        if analytics.num_positions == 0:
            return []

        concentration = analytics.concentration
        top_holding_pct = float(concentration.get("top_holding_pct", 0.0) or 0.0)
        top_3_pct = float(concentration.get("top_3_pct", 0.0) or 0.0)
        diversification_score = (
            analytics.diversification_score.score
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
                        f"Largest holding is {top_holding_pct:.1f}% of invested assets. "
                        "Open Holdings to review portfolio concentration."
                    ),
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
                        f"Top three holdings are {top_3_pct:.1f}% of invested assets. "
                        f"{diversification_detail}"
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

    def _recommendation_actions(self) -> list[dict[str, object]]:
        try:
            portfolio_size = get_effective_portfolio_totals(
                self.storage,
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

        actions: list[dict[str, object]] = []
        for recommendation in recommendations:
            decision = build_symbol_decision(
                symbol=recommendation.symbol,
                recommendation={
                    "action": "INITIATE_POSITION",
                    "reasoning": [f"Strong BUY signal ({recommendation.signal_strength}/10)"],
                },
                generated_at=recommendation.generated_at or recommendation.signal_date,
            ).model_dump(mode="json")
            confidence_badge = (
                "High"
                if recommendation.validation_type == "both"
                else "Medium"
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
                    ),
                    "action_label": "Open decision",
                    "href": f"/symbols/{recommendation.symbol}?tab=decision",
                    "symbol": recommendation.symbol,
                    "badge": confidence_badge,
                    "decision": decision,
                    "execution": {
                        "kind": "workflow_transition",
                        "symbol": recommendation.symbol,
                        "stage": "thesis_ready",
                    },
                    "_rank_score": action_rank_score(
                        "high",
                        impact=min(
                            numeric_value(recommendation.position_size_dollars) / 1000,
                            300.0,
                        ),
                        confidence=120.0
                        if recommendation.validation_type == "both"
                        else 60.0,
                        effort=80.0,
                    ),
                }
            )
        return actions

    def _jenny_actions(self) -> list[dict[str, object]]:
        try:
            dashboard = self._jenny_service().get_dashboard()
        except Exception as exc:
            logger.warning("home_action_jenny_failed", error=str(exc))
            return []

        actions: list[dict[str, object]] = []
        for notification in dashboard.notifications[:3]:
            portfolio_position = _portfolio_position_for_symbol(
                getattr(self, "storage", None),
                notification.symbol,
            )
            decision = build_symbol_decision(
                symbol=notification.symbol or "",
                recommendation=None,
                generated_at=notification.created_at,
                notifications=[notification],
                portfolio_position=portfolio_position,
            ).model_dump(mode="json")
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

    def _workflow_actions(self) -> list[dict[str, object]]:
        try:
            workflow_service = self._workflow_service()
        except Exception as exc:
            logger.warning("home_action_workflow_failed", error=str(exc))
            return []

        actions: list[dict[str, object]] = []
        for workflow in workflow_service.list_priority_workflows(limit=3):
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

    def _household_actions(self) -> list[dict[str, object]]:
        try:
            dashboard = self._household_service().get_dashboard()
        except Exception as exc:
            logger.warning("home_action_household_failed", error=str(exc))
            return []

        actions: list[dict[str, object]] = []
        items = list(dashboard.inbox)
        for index, item in enumerate(items[:4], start=1):
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
