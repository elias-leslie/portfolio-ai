"""Rules Validation Tasks.

Scheduled tasks for validating trading rules configuration and generating
optimization recommendations.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.agents.rules_validator_agent import (
    Recommendation,
    RulesValidatorAgent,
    ValidationReport,
)
from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.tasks._rules_validation_helpers import (
    _SQL_INSERT_ALERT,
    _SQL_INSERT_REPORT,
    _SQL_SIGNAL_STATS,
    _SQL_TRADE_STATS,
    _SQL_UPDATE_RECS,
    PerformanceData,
)

logger = get_logger(__name__)

TaskResult = dict[str, object]


def _store_validation_report(report: ValidationReport) -> None:
    """Persist a ValidationReport to rules_validation_reports."""
    error_dicts = [
        {
            "severity": e.severity, "category": e.category, "field_path": e.field_path,
            "message": e.message,
            "current_value": str(e.current_value) if e.current_value is not None else None,
            "expected_range": e.expected_range,
        }
        for e in report.errors
    ]
    with get_connection_manager().connection() as conn:
        raw_conn = conn.raw_connection
        with raw_conn.cursor() as cur:
            cur.execute(
                _SQL_INSERT_REPORT,
                (
                    report.rules_version, report.timestamp, report.overall_status,
                    sum(1 for e in report.errors if e.severity == "critical"),
                    sum(1 for e in report.errors if e.severity == "warning"),
                    sum(1 for e in report.errors if e.severity == "info"),
                    Jsonb(error_dicts), Jsonb([]), report.summary,
                ),
            )
        raw_conn.commit()


def _store_optimization_results(
    recommendations: list[Recommendation], performance_data: PerformanceData
) -> None:
    """Update the most recent validation report with recommendations."""
    rec_dicts = [
        {
            "priority": r.priority, "category": r.category, "field_path": r.field_path,
            "recommendation": r.recommendation, "rationale": r.rationale,
            "suggested_value": str(r.suggested_value) if r.suggested_value is not None else None,
        }
        for r in recommendations
    ]
    with get_connection_manager().connection() as conn:
        raw_conn = conn.raw_connection
        with raw_conn.cursor() as cur:
            perf_json = Jsonb(performance_data) if performance_data else None
            cur.execute(_SQL_UPDATE_RECS, (Jsonb(rec_dicts), perf_json))
        raw_conn.commit()


def _log_validation_result(report: ValidationReport) -> None:
    """Emit an appropriate log entry; store a DB alert for critical failures."""
    if report.overall_status == "valid":
        logger.info(
            "Rules validation passed",
            extra={"rules_version": report.rules_version,
                   "timestamp": report.timestamp.isoformat()},
        )
        return
    error_list = [
        {"severity": e.severity, "field": e.field_path, "message": e.message}
        for e in report.errors
    ]
    if report.overall_status == "warnings":
        logger.warning(
            f"Rules validation completed with warnings: {report.summary}",
            extra={"rules_version": report.rules_version,
                   "warning_count": sum(1 for e in report.errors if e.severity == "warning"),
                   "errors": error_list},
        )
        return
    critical_errors = [
        {"severity": e.severity, "field": e.field_path, "message": e.message,
         "current_value": e.current_value, "expected_range": e.expected_range}
        for e in report.errors if e.severity == "critical"
    ]
    logger.error(
        f"CRITICAL: Rules validation failed: {report.summary}",
        extra={"rules_version": report.rules_version,
               "critical_count": sum(1 for e in report.errors if e.severity == "critical"),
               "errors": critical_errors},
    )
    with get_connection_manager().connection() as conn:
        raw_conn = conn.raw_connection
        with raw_conn.cursor() as cur:
            cur.execute(
                _SQL_INSERT_ALERT,
                ("daily_rules_validation", "critical_failure", f"Rules validation failed: {report.summary}"),
            )
        raw_conn.commit()


def daily_rules_validation() -> TaskResult:
    """Validate trading rules configuration daily (03:00 UTC).

    Returns:
        Validation report summary
    """
    logger.info("Starting daily rules validation")
    try:
        validator = RulesValidatorAgent()
        report: ValidationReport = asyncio.run(validator.validate_rules())
        _store_validation_report(report)
        _log_validation_result(report)
        return {
            "status": report.overall_status,
            "rules_version": report.rules_version,
            "timestamp": report.timestamp.isoformat(),
            "error_count": len(report.errors),
            "summary": report.summary,
            "errors": [
                {"severity": e.severity, "category": e.category,
                 "field": e.field_path, "message": e.message}
                for e in report.errors
            ],
        }
    except Exception as exc:
        logger.error(f"Rules validation task failed: {exc}", exc_info=True)
        return {"status": "error", "error": str(exc)}


def weekly_optimization_review() -> TaskResult:
    """Generate optimization recommendations weekly (Monday 03:00 UTC).

    Returns:
        Optimization recommendations summary
    """
    logger.info("Starting weekly optimization review")
    try:
        performance_data = _get_recent_performance_data()
        validator = RulesValidatorAgent()
        recommendations: list[Recommendation] = asyncio.run(
            validator.generate_optimization_recommendations(performance_data)
        )
        _store_optimization_results(recommendations, performance_data)
        if recommendations:
            logger.info(f"Generated {len(recommendations)} optimization recommendations")
        else:
            logger.info("No optimization recommendations generated")
        return {
            "status": "completed",
            "timestamp": datetime.now(UTC).isoformat(),
            "recommendation_count": len(recommendations),
            "recommendations": [
                {"priority": r.priority, "category": r.category, "field": r.field_path,
                 "recommendation": r.recommendation, "rationale": r.rationale,
                 "suggested_value": r.suggested_value}
                for r in recommendations
            ],
        }
    except Exception as exc:
        logger.error(f"Optimization review task failed: {exc}", exc_info=True)
        return {"status": "error", "error": str(exc)}


def _get_recent_performance_data() -> PerformanceData:
    """Fetch recent trading performance metrics for optimization analysis.

    Returns:
        Performance metrics for last 30 days
    """
    try:
        with get_connection_manager().connection() as conn, conn.raw_connection.cursor(
            row_factory=dict_row
        ) as cur:
            cur.execute(_SQL_TRADE_STATS)
            trade_stats = cur.fetchone()
            cur.execute(_SQL_SIGNAL_STATS)
            signal_stats = cur.fetchall()
            return {
                "period_days": 30,
                "trade_stats": dict(trade_stats) if trade_stats else {},
                "signal_stats": [dict(row) for row in signal_stats],
            }
    except Exception as exc:
        logger.error(f"Failed to fetch performance data: {exc}", exc_info=True)
        return {}
