"""Private helpers for rules_validation_tasks.

Not part of the public API — import from rules_validation_tasks instead.
"""

from __future__ import annotations

from typing import Any

from psycopg2.extras import Json

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _serialise_errors(errors: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "severity": e.severity,
            "category": e.category,
            "field_path": e.field_path,
            "message": e.message,
            "current_value": str(e.current_value) if e.current_value is not None else None,
            "expected_range": e.expected_range,
        }
        for e in errors
    ]


def _serialise_recommendations(recommendations: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "priority": r.priority,
            "category": r.category,
            "field_path": r.field_path,
            "recommendation": r.recommendation,
            "rationale": r.rationale,
            "suggested_value": str(r.suggested_value) if r.suggested_value is not None else None,
        }
        for r in recommendations
    ]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def store_validation_report(report: Any) -> None:
    """Persist a validation report to rules_validation_reports."""
    with get_connection_manager().connection() as conn, conn._conn.cursor() as cur:
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
                Json(_serialise_errors(report.errors)),
                Json([]),  # Recommendations filled by weekly task
                report.summary,
            ),
        )
        conn._conn.commit()


def store_critical_alert(summary: str) -> None:
    """Record a critical validation failure in maintenance_log."""
    with get_connection_manager().connection() as conn, conn._conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO maintenance_log (task_name, status, message)
            VALUES (%s, %s, %s)
            """,
            (
                "daily_rules_validation",
                "critical_failure",
                f"Rules validation failed: {summary}",
            ),
        )
        conn._conn.commit()


def store_optimization_recommendations(
    recommendations: list[Any], performance_data: dict[str, Any]
) -> None:
    """Update the most recent validation report with optimization recommendations."""
    with get_connection_manager().connection() as conn, conn._conn.cursor() as cur:
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
                Json(_serialise_recommendations(recommendations)),
                Json(performance_data) if performance_data else None,
            ),
        )
        conn._conn.commit()


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------


def log_validation_result(report: Any) -> None:
    """Emit structured log lines for a completed validation report."""
    if report.overall_status == "valid":
        logger.info(
            "Rules validation passed",
            extra={
                "rules_version": report.rules_version,
                "timestamp": report.timestamp.isoformat(),
            },
        )
        return

    if report.overall_status == "warnings":
        logger.warning(
            f"Rules validation completed with warnings: {report.summary}",
            extra={
                "rules_version": report.rules_version,
                "warning_count": sum(1 for e in report.errors if e.severity == "warning"),
                "errors": [
                    {"severity": e.severity, "field": e.field_path, "message": e.message}
                    for e in report.errors
                ],
            },
        )
        return

    # critical
    logger.error(
        f"CRITICAL: Rules validation failed: {report.summary}",
        extra={
            "rules_version": report.rules_version,
            "critical_count": sum(1 for e in report.errors if e.severity == "critical"),
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


# ---------------------------------------------------------------------------
# Performance data fetch
# ---------------------------------------------------------------------------


def fetch_recent_performance_data() -> dict[str, Any]:
    """Fetch recent trading performance metrics for the last 30 days."""
    try:
        with get_connection_manager().connection() as conn, conn._conn.cursor() as cur:
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
                "trade_stats": (dict(trade_stats) if trade_stats else {}),
                "signal_stats": [dict(row) for row in signal_stats],
            }

    except Exception as e:
        logger.error(f"Failed to fetch performance data: {e}", exc_info=True)
        return {}
