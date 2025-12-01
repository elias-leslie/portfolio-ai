"""Unified data freshness monitoring service.

Monitors all critical data tables for staleness and creates maintenance_log alerts
when data becomes critically stale.

Design:
- Defines freshness thresholds per table (expected_hours, critical_hours)
- Checks MAX(date_column) for each table to determine age
- Trading day awareness: Skips weekend/holiday alerts for market data
- Creates maintenance_log entries for critical staleness
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, TypedDict

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.services.maintenance_tracker import record_maintenance_completion, record_maintenance_start

if TYPE_CHECKING:
    from app.storage.connection import ConnectionManager

logger = get_logger(__name__)


# Map tables to their refresh tasks for auto-remediation
REMEDIATION_TASKS: dict[str, str] = {
    "day_bars": "maintain_historical_market_data",
    "technical_indicators": "update_technical_indicators",
    "fear_greed_inputs": "populate_fear_greed_inputs",
    "fear_greed_daily": "calculate_fear_greed",
    "fear_greed_components": "calculate_fear_greed",  # Same task populates both tables
    "options_market_metrics": "fetch_options_activity_metrics",
    "news_cache": "refresh_news_sentiment",
    "reference_cache": "refresh_yfinance_reference_data",
    "watchlist_snapshots": "refresh_watchlist_scores",  # Refreshes watchlist scores
}


class TableFreshnessConfig(TypedDict):
    """Configuration for a single table's freshness monitoring."""

    table_name: str
    date_column: str
    expected_hours: int  # How often data should refresh
    critical_hours: int  # When to create alert
    market_data: bool  # Whether to skip alerts on weekends/holidays


# Freshness thresholds for all critical tables
TABLE_FRESHNESS_CONFIG: list[TableFreshnessConfig] = [
    {
        "table_name": "day_bars",
        "date_column": "date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
    },
    {
        "table_name": "technical_indicators",
        "date_column": "timestamp",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
    },
    {
        "table_name": "fear_greed_inputs",
        "date_column": "date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
    },
    {
        "table_name": "fear_greed_daily",
        "date_column": "as_of_date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
    },
    {
        "table_name": "fear_greed_components",
        "date_column": "as_of_date",
        "expected_hours": 24,
        "critical_hours": 48,
        "market_data": True,
    },
    {
        "table_name": "watchlist_snapshots",
        "date_column": "fetched_at",
        "expected_hours": 2,
        "critical_hours": 24,
        "market_data": False,  # Watchlist scores refresh continuously
    },
    {
        "table_name": "options_market_metrics",
        "date_column": "date",
        "expected_hours": 24,
        "critical_hours": 72,
        "market_data": True,
    },
    {
        "table_name": "news_cache",
        "date_column": "published_at",
        "expected_hours": 2,
        "critical_hours": 6,
        "market_data": False,
    },
    {
        "table_name": "reference_cache",
        "date_column": "fetched_at",
        "expected_hours": 24,
        "critical_hours": 72,
        "market_data": False,
    },
]


def _is_trading_day(now: dt.datetime | None = None) -> bool:
    """Check if today is a trading day (Monday-Friday, not checking holidays).

    Args:
        now: Current datetime. If None, uses current time in UTC.

    Returns:
        True if weekday (Mon-Fri), False if weekend

    Note:
        This does not account for market holidays. For full market hours check,
        use is_market_hours() from market_hours.py.
    """
    if now is None:
        now = dt.datetime.now(dt.UTC)

    # Monday=0, Sunday=6
    return now.weekday() < 5


def trigger_remediation(table_name: str, age_hours: float | None) -> str | None:
    """Trigger the appropriate refresh task for a stale table.

    Args:
        table_name: Name of the stale table
        age_hours: Age of the data in hours (None if no data)

    Returns:
        task_id if triggered, None if no remediation available
    """
    task_name = REMEDIATION_TASKS.get(table_name)
    if not task_name:
        logger.warning("no_remediation_task", table_name=table_name)
        return None

    # Use celery_app.send_task to trigger by name
    result = celery_app.send_task(task_name)
    task_id = str(result.id) if result.id else None
    logger.info(
        "remediation_triggered",
        table_name=table_name,
        task_name=task_name,
        task_id=task_id,
        age_hours=age_hours,
    )
    return task_id


def check_table_freshness(
    storage: ConnectionManager,
    config: TableFreshnessConfig,
    now: dt.datetime,
) -> dict[str, object]:
    """Check freshness for a single table.

    Args:
        storage: Database connection manager
        config: Table freshness configuration
        now: Current datetime for comparison

    Returns:
        Dict with table_name, last_update, age_hours, is_stale, is_critical
    """
    table_name = config["table_name"]
    date_column = config["date_column"]

    with storage.connection() as conn:
        # Query MAX(date_column) for this table
        result = conn.execute(
            f"""
            SELECT MAX({date_column}) as last_update
            FROM {table_name}
            """
        ).fetchone()

    last_update = result[0] if result else None

    if last_update is None:
        # Table is empty - critically stale
        return {
            "table_name": table_name,
            "last_update": None,
            "age_hours": None,
            "is_stale": True,
            "is_critical": True,
            "reason": "no_data",
        }

    # Ensure last_update is datetime
    if not isinstance(last_update, dt.datetime):
        logger.warning(
            "invalid_date_column_type",
            table=table_name,
            column=date_column,
            type=type(last_update).__name__,
        )
        return {
            "table_name": table_name,
            "last_update": None,
            "age_hours": None,
            "is_stale": True,
            "is_critical": True,
            "reason": "invalid_date",
        }

    # Make timezone-aware if needed
    if last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=dt.UTC)

    # Calculate age
    age = now - last_update
    age_hours = age.total_seconds() / 3600

    # Check staleness
    is_stale = age_hours > config["expected_hours"]
    is_critical = age_hours > config["critical_hours"]

    return {
        "table_name": table_name,
        "last_update": last_update.isoformat(),
        "age_hours": round(age_hours, 2),
        "is_stale": is_stale,
        "is_critical": is_critical,
        "reason": "age" if is_critical else None,
    }


def check_all_tables_freshness(storage: ConnectionManager, auto_remediate: bool = True) -> dict[str, object]:
    """Check freshness of all configured tables with optional auto-remediation.

    Args:
        storage: Database connection manager
        auto_remediate: If True, trigger refresh tasks for stale/critical tables

    Returns:
        Dict with tables_checked, fresh, stale, critical, alerts_created, remediations_triggered, details
    """
    now = dt.datetime.now(dt.UTC)
    is_trading = _is_trading_day(now)

    results = []
    alerts_created = 0
    remediations_triggered = 0

    for config in TABLE_FRESHNESS_CONFIG:
        try:
            result = check_table_freshness(storage, config, now)
            results.append(result)

            # Determine if we should take action
            should_remediate = False
            if result["is_critical"]:
                # Skip alerts for market data on weekends
                if config["market_data"] and not is_trading:
                    logger.info(
                        "skipping_weekend_alert",
                        table=config["table_name"],
                        reason="market_closed",
                    )
                    continue

                # Create maintenance_log alert
                age_hours_val = result["age_hours"]
                reason_val = result.get("reason", "age")
                create_staleness_alert(
                    table_name=config["table_name"],
                    age_hours=age_hours_val if isinstance(age_hours_val, (float, int, type(None))) else None,
                    threshold=config["critical_hours"],
                    reason=reason_val if isinstance(reason_val, str) else "unknown",
                )
                alerts_created += 1
                should_remediate = True
            elif result["is_stale"] and auto_remediate:
                # Even if not critical, remediate stale data
                should_remediate = True

            # Trigger remediation if needed
            if should_remediate and auto_remediate:
                age_hours_val = result["age_hours"]
                task_id = trigger_remediation(
                    table_name=config["table_name"],
                    age_hours=age_hours_val if isinstance(age_hours_val, (float, int, type(None))) else None,
                )
                if task_id:
                    remediations_triggered += 1

        except Exception as e:
            logger.error(
                "table_freshness_check_failed",
                table=config["table_name"],
                error=str(e),
            )
            results.append(
                {
                    "table_name": config["table_name"],
                    "last_update": None,
                    "age_hours": None,
                    "is_stale": True,
                    "is_critical": True,
                    "reason": f"check_failed: {e}",
                }
            )

    # Count statuses
    critical_count = sum(1 for r in results if r["is_critical"])
    stale_count = sum(1 for r in results if r["is_stale"])
    fresh_count = len(results) - stale_count

    return {
        "tables_checked": len(results),
        "fresh": fresh_count,
        "stale": stale_count,
        "critical": critical_count,
        "alerts_created": alerts_created,
        "remediations_triggered": remediations_triggered,
        "details": results,
    }


def create_staleness_alert(
    table_name: str,
    age_hours: float | None,
    threshold: int,
    reason: str,
) -> None:
    """Create maintenance_log entry for critical staleness.

    Args:
        table_name: Name of stale table
        age_hours: Age of data in hours (None if no data)
        threshold: Critical hours threshold
        reason: Reason code (no_data, age, invalid_date, etc.)
    """
    task_name = f"data_freshness_alert_{table_name}"

    # Record start
    log_id = record_maintenance_start(task_name=task_name, dry_run=False)

    # Build error message
    if reason == "no_data":
        error_message = f"Table '{table_name}' has no data (empty table)"
    elif reason == "invalid_date":
        error_message = f"Table '{table_name}' has invalid date column"
    elif age_hours is not None:
        error_message = (
            f"Table '{table_name}' is critically stale: "
            f"{age_hours:.1f} hours old (threshold: {threshold} hours)"
        )
    else:
        error_message = f"Table '{table_name}' freshness check failed: {reason}"

    # Record completion as error
    record_maintenance_completion(
        log_id=log_id,
        status="error",
        summary={
            "table_name": table_name,
            "age_hours": age_hours,
            "threshold_hours": threshold,
            "reason": reason,
        },
        error_message=error_message,
    )

    logger.warning(
        "staleness_alert_created",
        table=table_name,
        age_hours=age_hours,
        threshold=threshold,
        reason=reason,
    )
