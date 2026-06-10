"""Jenny operator task wrappers.

Thin wrappers so Hatchet schedules call the same service layer as the API.
"""

from __future__ import annotations

from typing import Any

from app.services.jenny_operator_service import JennyOperatorService


def run_daily_operator_task() -> dict[str, Any]:
    """Run Jenny's daily operator review."""
    result = JennyOperatorService().run_daily_operator(triggered_by="scheduled")
    return result.model_dump()


def run_weekly_learning_task() -> dict[str, Any]:
    """Run Jenny's weekly learning and scorecard refresh."""
    result = JennyOperatorService().run_weekly_learning(triggered_by="scheduled")
    return result.model_dump()


def run_daily_household_maintenance_task() -> dict[str, Any]:
    """Run Jenny's daily household-money maintenance pass."""
    result = JennyOperatorService().run_daily_household_maintenance(triggered_by="scheduled")
    payload = result.model_dump()
    payload["card_maintenance"] = _run_card_maintenance()
    return payload


def _run_card_maintenance() -> dict[str, Any]:
    """Daily card pass: monthly catalog research (marker-gated) + welcome/AF/
    rotation/pace alerts (plan §0a). Failures never break Jenny's maintenance."""
    from app.services.card_research_service import get_card_research_service
    from app.services.spend_alert_service import evaluate_and_dispatch

    summary: dict[str, Any] = {}
    catalog_changes: list[dict[str, Any]] = []
    try:
        research = get_card_research_service()
        if research.research_due():
            outcome = research.refresh_catalog(trigger="monthly")
            catalog_changes = list(outcome.get("material_changes") or [])
            summary["research"] = {
                "updates_applied": outcome.get("updates_applied"),
                "candidates_added": outcome.get("candidates_added"),
                "material_changes": len(catalog_changes),
            }
        else:
            summary["research"] = {"status": "not_due"}
    except Exception as exc:
        summary["research"] = {"status": "error", "error": str(exc)}
    try:
        dispatched = evaluate_and_dispatch(
            trigger="daily_maintenance", catalog_changes=catalog_changes
        )
        summary["alerts"] = [a.kind for a in dispatched]
    except Exception as exc:
        summary["alerts"] = {"status": "error", "error": str(exc)}
    return summary
