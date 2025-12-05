"""Rules Validation Celery Tasks.

Scheduled tasks for validating trading rules configuration and generating
optimization recommendations.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from psycopg2.extras import Json

from app.agents.rules_validator_agent import RulesValidatorAgent
from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)


@celery_app.task(name="daily_rules_validation")  # type: ignore[misc]
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
        # Run validation
        validator = RulesValidatorAgent()
        report = asyncio.run(validator.validate_rules())

        # Store validation report in database
        with get_connection_manager().connection() as conn:
            with conn._conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rules_validation_reports (
                        rules_version,
                        validation_time,
                        overall_status,
                        critical_count,
                        warning_count,
                        info_count,
                        validation_errors,
                        recommendations,
                        summary
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        report.rules_version,
                        report.timestamp,
                        report.overall_status,
                        sum(1 for e in report.errors if e.severity == "critical"),
                        sum(1 for e in report.errors if e.severity == "warning"),
                        sum(1 for e in report.errors if e.severity == "info"),
                        Json(
                            [
                                {
                                    "severity": e.severity,
                                    "category": e.category,
                                    "field_path": e.field_path,
                                    "message": e.message,
                                    "current_value": str(e.current_value)
                                    if e.current_value is not None
                                    else None,
                                    "expected_range": e.expected_range,
                                }
                                for e in report.errors
                            ]
                        ),
                        Json([]),  # Recommendations filled by weekly task
                        report.summary,
                    ),
                )
                conn._conn.commit()

        # Log results
        if report.overall_status == "valid":
            logger.info(
                "Rules validation passed",
                extra={
                    "rules_version": report.rules_version,
                    "timestamp": report.timestamp.isoformat(),
                },
            )
        elif report.overall_status == "warnings":
            logger.warning(
                f"Rules validation completed with warnings: {report.summary}",
                extra={
                    "rules_version": report.rules_version,
                    "warning_count": sum(
                        1 for e in report.errors if e.severity == "warning"
                    ),
                    "errors": [
                        {
                            "severity": e.severity,
                            "field": e.field_path,
                            "message": e.message,
                        }
                        for e in report.errors
                    ],
                },
            )
        else:  # critical
            logger.error(
                f"CRITICAL: Rules validation failed: {report.summary}",
                extra={
                    "rules_version": report.rules_version,
                    "critical_count": sum(
                        1 for e in report.errors if e.severity == "critical"
                    ),
                    "errors": [
                        {
                            "severity": e.severity,
                            "field": e.field_path,
                            "message": e.message,
                            "current_value": e.current_value,
                            "expected_range": e.expected_range,
                        }
                        for e in report.errors
                        if e.severity == "critical"
                    ],
                },
            )

            # Store critical alert in maintenance_log
            with get_connection_manager().connection() as conn:
                with conn._conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO maintenance_log (task_name, status, message)
                        VALUES (%s, %s, %s)
                        """,
                        (
                            "daily_rules_validation",
                            "critical_failure",
                            f"Rules validation failed: {report.summary}",
                        ),
                    )
                    conn._conn.commit()

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
        return {
            "status": "error",
            "error": str(e),
        }


@celery_app.task(name="weekly_optimization_review")  # type: ignore[misc]
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
        # Get recent performance data
        performance_data = _get_recent_performance_data()

        # Run optimization analysis
        validator = RulesValidatorAgent()
        recommendations = asyncio.run(
            validator.generate_optimization_recommendations(performance_data)
        )

        # Store recommendations in database (update most recent validation report)
        with get_connection_manager().connection() as conn:
            with conn._conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE rules_validation_reports
                    SET
                        recommendations = %s,
                        performance_data = %s
                    WHERE id = (
                        SELECT id FROM rules_validation_reports
                        ORDER BY validation_time DESC
                        LIMIT 1
                    )
                    """,
                    (
                        Json(
                            [
                                {
                                    "priority": r.priority,
                                    "category": r.category,
                                    "field_path": r.field_path,
                                    "recommendation": r.recommendation,
                                    "rationale": r.rationale,
                                    "suggested_value": str(r.suggested_value)
                                    if r.suggested_value is not None
                                    else None,
                                }
                                for r in recommendations
                            ]
                        ),
                        Json(performance_data) if performance_data else None,
                    ),
                )
                conn._conn.commit()

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
        return {
            "status": "error",
            "error": str(e),
        }


def _get_recent_performance_data() -> dict[str, Any]:
    """Fetch recent trading performance metrics for optimization analysis.

    Returns:
        Performance metrics for last 30 days
    """
    try:
        with get_connection_manager().connection() as conn:
            with conn._conn.cursor() as cur:
                # Get recent paper trade performance
                cur.execute(
                    """
                    SELECT
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END)::float / COUNT(*) as win_rate,
                        AVG(profit_loss) as avg_pnl,
                        STDDEV(profit_loss) as std_pnl,
                        MAX(drawdown_from_peak) as max_drawdown
                    FROM paper_trade_transactions
                    WHERE created_at >= NOW() - INTERVAL '30 days'
                        AND status = 'closed'
                    """
                )
                trade_stats = cur.fetchone()

                # Get signal classification stats
                cur.execute(
                    """
                    SELECT
                        signal_classification,
                        COUNT(*) as signal_count,
                        AVG(overall_score) as avg_score
                    FROM watchlist_snapshots_core
                    WHERE snapshot_time >= NOW() - INTERVAL '30 days'
                        AND signal_classification IS NOT NULL
                    GROUP BY signal_classification
                    ORDER BY signal_classification
                    """
                )
                signal_stats = cur.fetchall()

                return {
                    "period_days": 30,
                    "trade_stats": (
                        dict(trade_stats) if trade_stats else {}
                    ),
                    "signal_stats": [dict(row) for row in signal_stats],
                }

    except Exception as e:
        logger.error(f"Failed to fetch performance data: {e}", exc_info=True)
        return {}
