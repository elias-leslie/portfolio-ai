"""Rules Validation Tasks.

Scheduled tasks for validating trading rules configuration and generating
optimization recommendations.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.agents.rules_validator_agent import RulesValidatorAgent
from app.logging_config import get_logger
from app.tasks._rules_validation_helpers import (
    fetch_recent_performance_data,
    log_validation_result,
    store_critical_alert,
    store_optimization_recommendations,
    store_validation_report,
)

logger = get_logger(__name__)


def daily_rules_validation() -> dict[str, Any]:
    """Validate trading rules configuration daily.

    Schedule: Daily at 03:00 UTC

    Checks:
    - All thresholds in valid range (RSI 0-100, percentages 0-1, etc.)
    - No contradictory rules (logical consistency)
    - Fee assumptions realistic (commission not 0, slippage reasonable)
    - Position sizing sums valid (max positions * max size <= 100%)
    - All referenced indicators defined

    Logs validation results and alerts on critical failures.

    Returns:
        Validation report summary
    """
    logger.info("Starting daily rules validation")

    try:
        validator = RulesValidatorAgent()
        report = asyncio.run(validator.validate_rules())

        store_validation_report(report)
        log_validation_result(report)

        if report.overall_status == "critical":
            store_critical_alert(report.summary)

        return {
            "status": report.overall_status,
            "rules_version": report.rules_version,
            "timestamp": report.timestamp.isoformat(),
            "error_count": len(report.errors),
            "summary": report.summary,
            "errors": [
                {
                    "severity": e.severity,
                    "category": e.category,
                    "field": e.field_path,
                    "message": e.message,
                }
                for e in report.errors
            ],
        }

    except Exception as e:
        logger.error(f"Rules validation task failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def weekly_optimization_review() -> dict[str, Any]:
    """Generate optimization recommendations based on recent performance.

    Schedule: Weekly on Monday at 03:00 UTC

    Analysis:
    - Compare rules to recent performance
    - Identify unused rules
    - Propose threshold adjustments
    - Flag rules that never trigger

    Returns:
        Optimization recommendations summary
    """
    logger.info("Starting weekly optimization review")

    try:
        performance_data = _get_recent_performance_data()

        validator = RulesValidatorAgent()
        recommendations = asyncio.run(
            validator.generate_optimization_recommendations(performance_data)
        )

        store_optimization_recommendations(recommendations, performance_data)

        if recommendations:
            logger.info(
                f"Generated {len(recommendations)} optimization recommendations",
                extra={
                    "recommendations": [
                        {
                            "priority": r.priority,
                            "category": r.category,
                            "field": r.field_path,
                            "recommendation": r.recommendation,
                            "suggested_value": r.suggested_value,
                        }
                        for r in recommendations
                    ]
                },
            )
        else:
            logger.info("No optimization recommendations generated")

        return {
            "status": "completed",
            "timestamp": datetime.now(UTC).isoformat(),
            "recommendation_count": len(recommendations),
            "recommendations": [
                {
                    "priority": r.priority,
                    "category": r.category,
                    "field": r.field_path,
                    "recommendation": r.recommendation,
                    "rationale": r.rationale,
                    "suggested_value": r.suggested_value,
                }
                for r in recommendations
            ],
        }

    except Exception as e:
        logger.error(f"Optimization review task failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def _get_recent_performance_data() -> dict[str, Any]:
    """Fetch recent trading performance metrics for optimization analysis.

    Returns:
        Performance metrics for last 30 days
    """
    return fetch_recent_performance_data()
