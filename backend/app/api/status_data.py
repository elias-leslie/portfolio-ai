"""Data freshness and cache management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from datetime import date as date_type

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/status", tags=["status", "data"])


class CacheClearResponse(BaseModel):
    """Response for cache clear operation."""

    success: bool
    rows_deleted: int
    message: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


@router.post("/cache/clear", response_model=CacheClearResponse)
def clear_cache() -> CacheClearResponse:
    """Clear price cache table.

    Returns:
        CacheClearResponse: Result of cache clear operation
    """
    logger.info("clear_cache_request")

    try:
        mgr = get_connection_manager()
        with mgr.connection() as conn:
            # Delete all rows from price_cache table
            result = conn.execute("DELETE FROM price_cache")
            rows_deleted = result.rowcount if hasattr(result, "rowcount") else 0

        logger.info("clear_cache_success", rows_deleted=rows_deleted)
        return CacheClearResponse(
            success=True,
            rows_deleted=rows_deleted,
            message=f"Cleared {rows_deleted} cached price entries",
        )

    except Exception as e:
        logger.error("clear_cache_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {e!s}") from e


class TableFreshnessStatus(BaseModel):
    """Freshness status for a single table."""

    table_name: str = Field(description="Table name")
    last_updated: datetime | None = Field(description="Most recent timestamp in table")
    age_hours: float | None = Field(description="Age in hours since last update")
    status: str = Field(description="Status: fresh (within expected interval), stale (overdue)")
    row_count: int | None = Field(description="Total number of rows in table")
    expected_refresh_hours: int = Field(description="Expected refresh interval in hours")
    description: str = Field(description="Table description and update schedule")


class TableFreshnessResponse(BaseModel):
    """Response model for table freshness endpoint."""

    tables: list[TableFreshnessStatus] = Field(description="Freshness status for each table")
    fresh_count: int = Field(description="Number of fresh tables")
    stale_count: int = Field(description="Number of stale tables")
    critical_count: int = Field(description="Number of critical tables")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


@router.get("/table-freshness", response_model=TableFreshnessResponse)
async def get_table_freshness() -> TableFreshnessResponse:
    """Get freshness status for all important tables.

    Returns table-level freshness metrics:
    - fresh: Data updated within last 24 hours
    - stale: Data 24-48 hours old
    - critical: Data >48 hours old

    Tables monitored:
    - day_bars: OHLCV market data
    - fear_greed_inputs: F&G raw inputs
    - fear_greed_daily: F&G calculated scores
    - fear_greed_components: F&G component scores
    - news: News articles
    - watchlist_snapshots: Watchlist score snapshots
    - positions: Portfolio positions
    - accounts: Portfolio accounts
    - price_cache: Real-time price cache
    """
    try:
        conn_mgr = get_connection_manager()

        # Define tables with their timestamp columns and expected refresh intervals (in hours)
        table_configs = [
            ("day_bars", "date", "date", 24, "Daily OHLCV market data"),
            ("fear_greed_inputs", "as_of_date", "date", 24, "Fear & Greed raw inputs"),
            ("fear_greed_daily", "as_of_date", "date", 24, "Fear & Greed calculated scores"),
            ("fear_greed_components", "as_of_date", "date", 24, "Fear & Greed component scores"),
            (
                "technical_indicators",
                "calculated_at",
                "timestamp",
                24,
                "Daily technical indicators (RSI, MACD, etc.)",
            ),
            (
                "news_cache",
                "fetched_at",
                "timestamp",
                2,
                "News articles (refreshes every ~1min, 2h tolerance)",
            ),
            (
                "watchlist_snapshots",
                "fetched_at",
                "timestamp",
                2,
                "Watchlist scores (refreshes every ~1min, 2h tolerance)",
            ),
            ("price_cache", "cached_at", "timestamp", 1, "Real-time price cache (on-demand)"),
            ("ml_model_metrics", "trained_at", "timestamp", 24, "ML model training metrics"),
            ("source_metrics", "calculated_at", "timestamp", 12, "News source quality profiling"),
        ]

        tables: list[TableFreshnessStatus] = []
        now = datetime.now(UTC)

        with conn_mgr.connection() as conn:
            # Validate all table and column names exist before executing queries
            # This prevents SQL injection by verifying configuration against schema
            validated_configs = []
            for table_name, timestamp_col, col_type, expected_hours, desc in table_configs:
                try:
                    # Check table exists in information_schema
                    table_check = conn.execute(
                        """
                        SELECT EXISTS(
                            SELECT 1 FROM information_schema.tables
                            WHERE table_schema = 'public' AND table_name = %s
                        )
                        """,
                        [table_name],
                    )
                    row = table_check.fetchone()
                    table_exists = row[0] if row else False

                    if not table_exists:
                        logger.warning(
                            f"table_not_found_{table_name}",
                            table=table_name,
                        )
                        continue

                    # Check column exists in table
                    col_check = conn.execute(
                        """
                        SELECT EXISTS(
                            SELECT 1 FROM information_schema.columns
                            WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
                        )
                        """,
                        [table_name, timestamp_col],
                    )
                    row = col_check.fetchone()
                    col_exists = row[0] if row else False

                    if not col_exists:
                        logger.warning(
                            f"column_not_found_{table_name}_{timestamp_col}",
                            table=table_name,
                            column=timestamp_col,
                        )
                        continue

                    # validated: table/column from information_schema
                    validated_configs.append(
                        (table_name, timestamp_col, col_type, expected_hours, desc)
                    )
                except Exception as e:
                    logger.warning(
                        f"failed_to_validate_config_{table_name}",
                        error=str(e),
                    )
                    continue

            for table_name, timestamp_col, col_type, expected_hours, desc in validated_configs:
                try:
                    # Get latest timestamp
                    # validated: table/column from information_schema
                    result = conn.execute(f"SELECT MAX({timestamp_col}) FROM {table_name}")
                    row = result.fetchone()
                    last_updated_raw = row[0] if row else None

                    # Get row count
                    # validated: table/column from information_schema
                    result = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    row = result.fetchone()
                    row_count = row[0] if row else 0
                    if not isinstance(row_count, int):
                        row_count = int(row_count) if row_count else 0

                    # Calculate age and status based on expected refresh interval
                    age_hours = None
                    status = "unknown"
                    last_updated = None

                    if last_updated_raw:
                        # Convert date to datetime for age calculation
                        if col_type == "date":
                            if isinstance(last_updated_raw, str):
                                parsed_date = date_type.fromisoformat(last_updated_raw)
                                last_updated = datetime.combine(
                                    parsed_date, datetime.min.time(), tzinfo=UTC
                                )
                            elif isinstance(last_updated_raw, date_type):
                                # Already a date object (psycopg2 returns date)
                                last_updated = datetime.combine(
                                    last_updated_raw, datetime.min.time(), tzinfo=UTC
                                )
                            else:
                                # Unexpected type for date field, mark as unknown
                                last_updated = None
                        elif isinstance(last_updated_raw, datetime):
                            last_updated = last_updated_raw
                        else:
                            last_updated = None

                        if last_updated is not None:
                            age_delta = now - last_updated
                            age_hours = age_delta.total_seconds() / 3600

                            # Status based on expected interval with 2x tolerance
                            if age_hours <= expected_hours:
                                status = "fresh"
                            elif age_hours <= expected_hours * 2:
                                status = "stale"
                            else:
                                status = "critical"

                    tables.append(
                        TableFreshnessStatus(
                            table_name=table_name,
                            last_updated=last_updated,
                            age_hours=age_hours,
                            status=status,
                            row_count=row_count,
                            expected_refresh_hours=expected_hours,
                            description=desc,
                        )
                    )

                except Exception as e:
                    logger.warning(f"failed_to_check_freshness_{table_name}", error=str(e))
                    # Add table with unknown status
                    tables.append(
                        TableFreshnessStatus(
                            table_name=table_name,
                            last_updated=None,
                            age_hours=None,
                            status="error",
                            row_count=0,
                            expected_refresh_hours=0,
                            description="Error checking table",
                        )
                    )

        # Calculate summary counts
        fresh_count = sum(1 for t in tables if t.status == "fresh")
        stale_count = sum(1 for t in tables if t.status == "stale")
        critical_count = sum(1 for t in tables if t.status == "critical")

        return TableFreshnessResponse(
            tables=tables,
            fresh_count=fresh_count,
            stale_count=stale_count,
            critical_count=critical_count,
        )

    except Exception as e:
        logger.error("failed_to_fetch_table_freshness", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch table freshness: {e}") from e
