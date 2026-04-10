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
from app.portfolio.totals import get_live_portfolio_totals
from app.services.household_finance_service import HouseholdFinanceService
from app.services.jenny_operator_service import JennyOperatorService
from app.services.symbol_workflow_service import SymbolWorkflowService
from app.storage import get_storage

logger = get_logger(__name__)

PRIORITY_RANK = {
    "critical": 0,
    "high": 1,
    "warning": 2,
    "medium": 3,
    "low": 4,
}


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

        deduped: list[dict[str, object]] = []
        seen: set[tuple[object, object, object]] = set()
        for action in actions:
            key = (action.get("title"), action.get("href"), action.get("symbol"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(action)

        deduped.sort(
            key=lambda action: (
                PRIORITY_RANK.get(str(action.get("priority", "low")), 99),
                str(action.get("title", "")),
            )
        )
        queue = deduped[:8]
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
            return [
                {
                    "id": "portfolio-health-top-holding",
                    "source": "portfolio",
                    "category": "investing",
                    "priority": "high" if top_holding_pct >= 50 else "warning",
                    "title": "Portfolio needs a concentration check",
                    "detail": (
                        f"Largest holding is {top_holding_pct:.1f}% of the portfolio. "
                        "Open Investing to review portfolio concentration."
                    ),
                    "action_label": "Review investing",
                    "href": "/portfolio#portfolio-overview",
                    "symbol": None,
                    "badge": "Concentration",
                }
            ]

        if top_3_pct >= 70 or (diversification_score is not None and diversification_score < 50):
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
                        f"Top three holdings are {top_3_pct:.1f}% of the portfolio. "
                        f"{diversification_detail}"
                    ),
                    "action_label": "Review investing",
                    "href": "/portfolio#portfolio-overview",
                    "symbol": None,
                    "badge": "Portfolio",
                }
            ]

        return []

    def _recommendation_actions(self) -> list[dict[str, object]]:
        try:
            portfolio_size = get_live_portfolio_totals(
                self.storage,
                include_paper=False,
            ).cash_inclusive_total_value
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
            decision = build_symbol_decision(
                symbol=notification.symbol or "",
                recommendation=None,
                generated_at=notification.created_at,
                notifications=[notification],
                portfolio_position=_portfolio_position_for_symbol(
                    getattr(self, "storage", None),
                    notification.symbol,
                ),
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
        unsatisfied = [n for n in dashboard.jenny_needs if n.status == "unsatisfied"]
        for index, need in enumerate(unsatisfied[:3], start=1):
            actions.append(
                {
                    "id": f"household-{index}-{need.need_type}",
                    "source": "household",
                    "category": "household",
                    "priority": need.priority,
                    "title": need.title,
                    "detail": need.detail,
                    "action_label": "Resolve",
                    "href": need.action_href or "/money",
                    "symbol": None,
                    "badge": "Household",
                }
            )

        return actions
