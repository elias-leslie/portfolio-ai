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
from typing import TYPE_CHECKING

from app.hatchet_app import get_admin_client
from app.logging_config import get_logger
from app.services._data_freshness_config import (
    REMEDIATION_TASKS,
    TABLE_FRESHNESS_CONFIG,
    TableFreshnessConfig,
)
from app.services.maintenance_tracker import record_maintenance_completion, record_maintenance_start
from app.utils.market_hours import (
    NY_TZ,
    get_market_aware_age_hours,
    get_market_close_time,
    is_market_open,
    is_trading_day,
)

if TYPE_CHECKING:
    from app.storage.connection import ConnectionManager

# Re-export config types so existing callers importing from this module still work
__all__ = [
    "REMEDIATION_TASKS",
    "TABLE_FRESHNESS_CONFIG",
    "TableFreshnessConfig",
    "check_all_tables_freshness",
    "check_table_freshness",
    "clear_remediation_cooldown",
    "create_staleness_alert",
    "get_remediation_cooldowns",
    "trigger_remediation",
]

logger = get_logger(__name__)

# Remediation cooldown tracking (in-memory, resets on service restart)
# Maps table_name -> last_remediation_timestamp
_remediation_cooldowns: dict[str, dt.datetime] = {}
REMEDIATION_COOLDOWN_MINUTES = 30


# ---------------------------------------------------------------------------
# Cooldown helpers
# ---------------------------------------------------------------------------


def get_remediation_cooldowns() -> dict[str, str]:
    """Get current remediation cooldowns for visibility in health endpoints."""
    return {table: ts.isoformat() for table, ts in _remediation_cooldowns.items()}


def clear_remediation_cooldown(table_name: str) -> None:
    """Clear cooldown for a table after successful data refresh."""
    if table_name in _remediation_cooldowns:
        del _remediation_cooldowns[table_name]
        logger.info("remediation_cooldown_cleared", table_name=table_name)


def _is_in_cooldown(table_name: str, now: dt.datetime) -> bool:
    last_attempt = _remediation_cooldowns.get(table_name)
    if last_attempt is None:
        return False
    return (now - last_attempt) < dt.timedelta(minutes=REMEDIATION_COOLDOWN_MINUTES)


def _can_remediate(table_name: str, is_market_data: bool, now: dt.datetime) -> bool:
    """Return True if remediation should proceed (not in cooldown, market open if needed)."""
    if _is_in_cooldown(table_name, now):
        logger.info("remediation_skipped_cooldown", table_name=table_name, reason="in_cooldown")
        return False
    if is_market_data and not is_market_open(now):
        logger.info("remediation_skipped_market_closed", table_name=table_name, reason="market_closed")
        return False
    return True


def trigger_remediation(
    table_name: str,
    age_hours: float | None,
    is_market_data: bool = False,
) -> str | None:
    """Trigger the appropriate refresh task for a stale table.

    Includes thrashing protection:
    - Won't retry same table within 30 minutes
    - Won't attempt market data remediation if market is closed

    Returns task_id if triggered, None if skipped or no remediation available.
    """
    now = dt.datetime.now(dt.UTC)
    if not _can_remediate(table_name, is_market_data, now):
        return None
    task_name = REMEDIATION_TASKS.get(table_name)
    if not task_name:
        logger.warning("no_remediation_task", table_name=table_name)
        return None
    _remediation_cooldowns[table_name] = now
    admin = get_admin_client()
    result = admin.run_workflow(task_name, {})
    task_id = str(result.workflow_run_id) if result else None
    logger.info("remediation_triggered", table_name=table_name, task_name=task_name, task_id=task_id, age_hours=age_hours)
    return task_id


# ---------------------------------------------------------------------------
# Freshness query helpers
# ---------------------------------------------------------------------------


def _build_freshness_query(table_name: str, date_column: str, where_clause: str | None) -> str:
    base = f"SELECT MAX({date_column}) as last_update\nFROM {table_name}"
    return f"{base}\nWHERE {where_clause}" if where_clause else base


def _fetch_last_update(storage: ConnectionManager, query: str) -> object:
    with storage.connection() as conn:
        result = conn.execute(query).fetchone()
    return result[0] if result else None


def _coerce_to_datetime(
    last_update: object,
    table_name: str,
    date_column: str,
    is_market_data: bool,
) -> dt.datetime | None:
    """Coerce a DATE or DATETIME value to a timezone-aware datetime."""
    if isinstance(last_update, dt.datetime):
        return last_update if last_update.tzinfo else last_update.replace(tzinfo=dt.UTC)
    if isinstance(last_update, dt.date):
        if is_market_data:
            return dt.datetime.combine(last_update, get_market_close_time(last_update), tzinfo=NY_TZ)
        return dt.datetime.combine(last_update, dt.time.min, tzinfo=dt.UTC)
    logger.warning("invalid_date_column_type", table=table_name, column=date_column, type=type(last_update).__name__)
    return None


def _stale_result(table_name: str, reason: str) -> dict[str, object]:
    return {"table_name": table_name, "last_update": None, "age_hours": None, "is_stale": True, "is_critical": True, "reason": reason}


def check_table_freshness(
    storage: ConnectionManager,
    config: TableFreshnessConfig,
    now: dt.datetime,
) -> dict[str, object]:
    """Check freshness for a single table.

    Returns dict with table_name, last_update, age_hours, is_stale, is_critical.
    """
    table_name = config["table_name"]
    date_column = config["date_column"]
    query = _build_freshness_query(table_name, date_column, config.get("where_clause"))
    raw = _fetch_last_update(storage, query)
    if raw is None:
        return _stale_result(table_name, "no_data")
    last_update = _coerce_to_datetime(raw, table_name, date_column, config["market_data"])
    if last_update is None:
        return _stale_result(table_name, "invalid_date")
    age_hours = get_market_aware_age_hours(last_update=last_update, now=now, is_market_data=config["market_data"])
    age_hours = max(0.0, age_hours - config.get("availability_delay_hours", 0.0))
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


# ---------------------------------------------------------------------------
# Bulk check helpers
# ---------------------------------------------------------------------------


def _as_age_hours(value: object) -> float | None:
    return value if isinstance(value, (float, int, type(None))) else None


def _handle_critical_result(config: TableFreshnessConfig, result: dict[str, object], auto_remediate: bool) -> int:
    """Create a staleness alert and optionally trigger remediation. Returns remediations triggered."""
    age_hours = _as_age_hours(result.get("age_hours"))
    reason = result.get("reason")
    create_staleness_alert(
        table_name=config["table_name"],
        age_hours=age_hours,
        threshold=config["critical_hours"],
        reason=reason if isinstance(reason, str) else "unknown",
    )
    if not auto_remediate:
        return 0
    task_id = trigger_remediation(table_name=config["table_name"], age_hours=age_hours, is_market_data=config["market_data"])
    return 1 if task_id else 0


def _should_suppress_alert(config: TableFreshnessConfig, result: dict[str, object], is_trading: bool) -> bool:
    """Return True if a critical alert should be suppressed due to weekend/holiday."""
    # Maximum time a weekend/holiday suppression is allowed to hide a real failure.
    max_weekend_suppression_hours = 24
    age_hours = _as_age_hours(result.get("age_hours"))
    return (
        config["market_data"]
        and not is_trading
        and age_hours is not None
        and age_hours < max_weekend_suppression_hours
    )


def _check_one_table(
    storage: ConnectionManager,
    config: TableFreshnessConfig,
    now: dt.datetime,
    is_trading: bool,
    auto_remediate: bool,
) -> tuple[dict[str, object], int, int]:
    """Check a single table and return (result, alerts_created, remediations_triggered)."""
    try:
        result = check_table_freshness(storage, config, now)
    except Exception as e:
        logger.error("table_freshness_check_failed", table=config["table_name"], error=str(e), exc_info=True)
        return (
            {"table_name": config["table_name"], "last_update": None, "age_hours": None,
             "is_stale": True, "is_critical": True, "reason": f"check_failed: {e}"},
            0, 0,
        )

    if result["is_critical"]:
        if _should_suppress_alert(config, result, is_trading):
            logger.info("skipping_weekend_alert", table=config["table_name"], reason="market_closed", age_hours=_as_age_hours(result.get("age_hours")))
            return result, 0, 0
        triggered = _handle_critical_result(config, result, auto_remediate)
        return result, 1, triggered

    if result["is_stale"] and auto_remediate:
        age_hours = _as_age_hours(result.get("age_hours"))
        task_id = trigger_remediation(table_name=config["table_name"], age_hours=age_hours, is_market_data=config["market_data"])
        return result, 0, 1 if task_id else 0

    return result, 0, 0


def check_all_tables_freshness(storage: ConnectionManager, auto_remediate: bool = True) -> dict[str, object]:
    """Check freshness of all configured tables with optional auto-remediation."""
    now = dt.datetime.now(dt.UTC)
    is_trading = is_trading_day(now.date())
    results: list[dict[str, object]] = []
    alerts_created = 0
    remediations_triggered = 0

    for config in TABLE_FRESHNESS_CONFIG:
        result, alerts, triggered = _check_one_table(storage, config, now, is_trading, auto_remediate)
        results.append(result)
        alerts_created += alerts
        remediations_triggered += triggered

    critical_count = sum(1 for r in results if r["is_critical"])
    stale_count = sum(1 for r in results if r["is_stale"])
    return {
        "tables_checked": len(results),
        "fresh": len(results) - stale_count,
        "stale": stale_count,
        "critical": critical_count,
        "alerts_created": alerts_created,
        "remediations_triggered": remediations_triggered,
        "details": results,
    }


# ---------------------------------------------------------------------------
# Alert helpers
# ---------------------------------------------------------------------------


def _build_error_message(table_name: str, age_hours: float | None, threshold: int, reason: str) -> str:
    if reason == "no_data":
        return f"Table '{table_name}' has no data (empty table)"
    if reason == "invalid_date":
        return f"Table '{table_name}' has invalid date column"
    if age_hours is not None:
        return f"Table '{table_name}' is critically stale: {age_hours:.1f} hours old (threshold: {threshold} hours)"
    return f"Table '{table_name}' freshness check failed: {reason}"


def create_staleness_alert(table_name: str, age_hours: float | None, threshold: int, reason: str) -> None:
    """Create maintenance_log entry for critical staleness."""
    task_name = f"data_freshness_alert_{table_name}"
    log_id = record_maintenance_start(task_name=task_name, dry_run=False)
    error_message = _build_error_message(table_name, age_hours, threshold, reason)
    record_maintenance_completion(
        log_id=log_id,
        status="error",
        summary={"table_name": table_name, "age_hours": age_hours, "threshold_hours": threshold, "reason": reason},
        error_message=error_message,
    )
    logger.warning("staleness_alert_created", table=table_name, age_hours=age_hours, threshold=threshold, reason=reason)
