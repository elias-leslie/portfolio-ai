"""Aggregate prioritized product actions for the home page."""

from __future__ import annotations

from datetime import UTC, datetime

from app.api.recommendations.logic import DEFAULT_POSITION_PCT
from app.api.recommendations.queries import fetch_recommendations
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


class HomeActionService:
    """Build a ranked cross-product action queue for the home dashboard."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.household_service = HouseholdFinanceService()
        self.jenny_service = JennyOperatorService()
        self.workflow_service = SymbolWorkflowService()

    def get_action_queue(self) -> dict[str, object]:
        actions: list[dict[str, object]] = []
        actions.extend(self._recommendation_actions())
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
                    "title": f"Review {recommendation.symbol}",
                    "detail": (
                        f"{recommendation.signal_type} signal at {recommendation.signal_strength}/10. "
                        f"Suggested size ${recommendation.position_size_dollars:,.0f}."
                    ),
                    "action_label": "Open symbol",
                    "href": f"/symbols/{recommendation.symbol}",
                    "symbol": recommendation.symbol,
                    "badge": confidence_badge,
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
            dashboard = self.jenny_service.get_dashboard()
        except Exception as exc:
            logger.warning("home_action_jenny_failed", error=str(exc))
            return []

        actions: list[dict[str, object]] = []
        for notification in dashboard.notifications[:3]:
            href = f"/symbols/{notification.symbol}" if notification.symbol else "/portfolio"
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
                    "title": notification.title,
                    "detail": notification.recommendation or notification.detail,
                    "action_label": "Review with Jenny",
                    "href": href,
                    "symbol": notification.symbol,
                    "badge": notification.severity.title(),
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
                    "href": f"/symbols/{review.symbol}",
                    "symbol": review.symbol,
                    "badge": review.outcome_label.title(),
                }
            )

        return actions

    def _workflow_actions(self) -> list[dict[str, object]]:
        workflow_service = getattr(self, "workflow_service", None)
        if workflow_service is None:
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
                        "detail": "A review is due before this symbol keeps moving through the workflow.",
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
                        "detail": "Keep this name out of the active loop unless the thesis is rebuilt.",
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
            dashboard = self.household_service.get_dashboard()
        except Exception as exc:
            logger.warning("home_action_household_failed", error=str(exc))
            return []

        actions: list[dict[str, object]] = []
        for index, item in enumerate(dashboard.action_items[:3], start=1):
            actions.append(
                {
                    "id": f"household-{index}-{item.source}",
                    "source": "household",
                    "category": "household",
                    "priority": item.priority,
                    "title": item.title,
                    "detail": item.detail,
                    "action_label": item.action_label,
                    "href": item.href,
                    "symbol": None,
                    "badge": "Household",
                }
            )

        return actions
