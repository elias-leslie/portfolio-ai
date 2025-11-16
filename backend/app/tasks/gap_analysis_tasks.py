"""Celery tasks for trading intelligence gap analysis and monitoring.

Tasks:
- analyze_trading_gaps: Daily gap analysis after capabilities scan
- track_gap_trends: Historical trending analysis
- alert_critical_gaps: Alert on new critical gaps
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.celery_app import celery_app
from app.services.gap_detection import GapDetector
from app.storage.connection import ConnectionManager

logger = logging.getLogger(__name__)


@celery_app.task(name="analyze_trading_gaps")  # type: ignore[misc]
def analyze_trading_gaps() -> dict[str, Any]:
    """Analyze trading intelligence gaps.

    Runs daily after capabilities scan (03:30 UTC).
    Analyzes new gaps, resolved gaps, coverage trends.

    Returns:
        dict: Analysis results with gap counts and coverage metrics
    """
    logger.info("Starting trading gaps analysis...")

    try:
        # Initialize connection manager and gap detector
        conn_mgr = ConnectionManager()
        detector = GapDetector(conn_mgr)

        # Run gap analysis
        result = detector.analyze_gaps()

        # Calculate average coverage from analysis_types
        total_coverage = sum(at["coverage_pct"] for at in result["analysis_types"].values())
        avg_coverage_pct = (
            total_coverage / len(result["analysis_types"]) if result["analysis_types"] else 0.0
        )

        # Save to gap_analysis_history table
        with conn_mgr.connection() as conn:
            conn.execute(
                """
                INSERT INTO gap_analysis_history (
                    analysis_timestamp,
                    total_gaps,
                    p0_gaps,
                    p1_gaps,
                    p2_gaps,
                    p3_gaps,
                    avg_coverage_pct,
                    analysis_results
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                [
                    datetime.now(UTC),
                    result["total_gaps"],
                    result["p0_gaps"],
                    result["p1_gaps"],
                    result["p2_gaps"],
                    result["p3_gaps"],
                    avg_coverage_pct,
                    result,  # TypedDict is already a dict
                ],
            )
            conn.commit()

        logger.info(
            f"Gap analysis complete: {result['total_gaps']} total gaps, "
            f"avg coverage {avg_coverage_pct:.1f}%"
        )

        return {
            "status": "success",
            "timestamp": datetime.now(UTC).isoformat(),
            "total_gaps": result["total_gaps"],
            "p0_gaps": result["p0_gaps"],
            "p1_gaps": result["p1_gaps"],
            "p2_gaps": result["p2_gaps"],
            "p3_gaps": result["p3_gaps"],
            "avg_coverage_pct": avg_coverage_pct,
        }

    except Exception as e:
        logger.error(f"Gap analysis failed: {e}", exc_info=True)
        return {
            "status": "error",
            "timestamp": datetime.now(UTC).isoformat(),
            "error": str(e),
        }


@celery_app.task(name="track_gap_trends")  # type: ignore[misc]
def track_gap_trends() -> dict[str, Any]:
    """Track gap coverage trends over time.

    Analyzes historical gap_analysis_history table to identify:
    - Coverage improvements (gaps filled)
    - Coverage regressions (new gaps or data staleness)
    - Long-term trends

    Returns:
        dict: Trend analysis with coverage deltas
    """
    logger.info("Analyzing gap coverage trends...")

    try:
        conn_mgr = ConnectionManager()

        with conn_mgr.connection() as conn:
            # Get last 30 days of gap analysis
            rows = conn.execute(
                """
                SELECT
                    analysis_timestamp,
                    total_gaps,
                    avg_coverage_pct
                FROM gap_analysis_history
                WHERE analysis_timestamp >= NOW() - INTERVAL '30 days'
                ORDER BY analysis_timestamp DESC
                """
            ).fetchall()

        if len(rows) < 2:
            return {
                "status": "insufficient_data",
                "message": "Need at least 2 data points for trend analysis",
            }

        # Calculate trends
        latest = rows[0]
        previous = rows[1]
        month_ago = rows[-1]

        gap_delta = latest[1] - previous[1]
        coverage_delta = latest[2] - previous[2]
        month_gap_delta = latest[1] - month_ago[1]
        month_coverage_delta = latest[2] - month_ago[2]

        logger.info(
            f"Trend analysis: {gap_delta:+d} gaps (24h), "
            f"{coverage_delta:+.1f}% coverage (24h), "
            f"{month_gap_delta:+d} gaps (30d), "
            f"{month_coverage_delta:+.1f}% coverage (30d)"
        )

        trend = (
            "improving" if coverage_delta > 0 else "declining" if coverage_delta < 0 else "stable"
        )

        return {
            "status": "success",
            "timestamp": datetime.now(UTC).isoformat(),
            "current_gaps": latest[1],
            "current_coverage_pct": float(latest[2]),
            "delta_24h": {
                "gaps": gap_delta,
                "coverage_pct": float(coverage_delta),
            },
            "delta_30d": {
                "gaps": month_gap_delta,
                "coverage_pct": float(month_coverage_delta),
            },
            "trend": trend,
        }

    except Exception as e:
        logger.error(f"Gap trend analysis failed: {e}", exc_info=True)
        return {
            "status": "error",
            "timestamp": datetime.now(UTC).isoformat(),
            "error": str(e),
        }


def _alert_p0_gaps(conn_mgr: ConnectionManager, p0_gaps: int, total_gaps: int) -> int:
    """Create alert for P0 (critical) gaps.

    Args:
        conn_mgr: Database connection manager
        p0_gaps: Number of P0 gaps detected
        total_gaps: Total number of gaps

    Returns:
        1 if alert created, 0 otherwise
    """
    if p0_gaps <= 0:
        return 0

    with conn_mgr.connection() as conn:
        conn.execute(
            """
            INSERT INTO status_logs (
                component,
                level,
                message,
                metadata,
                timestamp
            ) VALUES (
                'gap_detector',
                'warning',
                %s,
                %s,
                %s
            )
            """,
            [
                f"{p0_gaps} critical gaps (P0) blocking trading strategies",
                {"p0_gaps": p0_gaps, "total_gaps": total_gaps},
                datetime.now(UTC),
            ],
        )
        conn.commit()
    return 1


def _alert_low_coverage(
    conn_mgr: ConnectionManager,
    analysis_types: dict[str, Any],
    threshold: float = 50.0,
) -> int:
    """Create alerts for analysis types with low coverage.

    Args:
        conn_mgr: Database connection manager
        analysis_types: Dict of analysis type results with coverage metrics
        threshold: Coverage threshold percentage (default 50%)

    Returns:
        Number of alerts created
    """
    alerts_created = 0

    for analysis_type, coverage_result in analysis_types.items():
        if coverage_result["coverage_pct"] < threshold:
            with conn_mgr.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO status_logs (
                        component,
                        level,
                        message,
                        metadata,
                        timestamp
                    ) VALUES (
                        'gap_detector',
                        'warning',
                        %s,
                        %s,
                        %s
                    )
                    """,
                    [
                        f"{analysis_type} coverage critically low: {coverage_result['coverage_pct']:.1f}%",
                        {
                            "analysis_type": analysis_type,
                            "coverage_pct": coverage_result["coverage_pct"],
                            "missing_capabilities": coverage_result["missing_capabilities"],
                        },
                        datetime.now(UTC),
                    ],
                )
                conn.commit()
            alerts_created += 1

    return alerts_created


@celery_app.task(name="alert_critical_gaps")  # type: ignore[misc]
def alert_critical_gaps() -> dict[str, Any]:
    """Alert on critical gaps (P0 priority).

    Creates status log entries when:
    - New P0 gaps appear
    - Coverage drops below threshold (e.g., <50% for any analysis type)

    Returns:
        dict: Alert status with critical gap count
    """
    logger.info("Checking for critical gaps...")

    try:
        conn_mgr = ConnectionManager()
        detector = GapDetector(conn_mgr)

        # Run gap analysis
        result = detector.analyze_gaps()

        alerts_created = 0
        alerts_created += _alert_p0_gaps(conn_mgr, result["p0_gaps"], result["total_gaps"])
        alerts_created += _alert_low_coverage(conn_mgr, result["analysis_types"])

        logger.info(f"Critical gap check complete: {alerts_created} alerts created")

        # Calculate average coverage from analysis_types
        total_coverage = sum(at["coverage_pct"] for at in result["analysis_types"].values())
        avg_coverage_pct = (
            total_coverage / len(result["analysis_types"]) if result["analysis_types"] else 0.0
        )

        return {
            "status": "success",
            "timestamp": datetime.now(UTC).isoformat(),
            "p0_gaps": result["p0_gaps"],
            "alerts_created": alerts_created,
            "avg_coverage_pct": avg_coverage_pct,
        }

    except Exception as e:
        logger.error(f"Critical gap alert failed: {e}", exc_info=True)
        return {
            "status": "error",
            "timestamp": datetime.now(UTC).isoformat(),
            "error": str(e),
        }
