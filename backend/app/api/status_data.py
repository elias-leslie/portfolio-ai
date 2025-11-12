"""Data freshness and cache management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

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
    - watchlist_items: User watchlist entries
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
                "watchlist_items",
                "updated_at",
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
            for table_name, timestamp_col, col_type, expected_hours, desc in table_configs:
                try:
                    # Get latest timestamp
                    result = conn.execute(f"SELECT MAX({timestamp_col}) FROM {table_name}")
                    row = result.fetchone()
                    last_updated = row[0] if row else None

                    # Get row count
                    result = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    row = result.fetchone()
                    row_count = row[0] if row else 0

                    # Calculate age and status based on expected refresh interval
                    age_hours = None
                    status = "unknown"

                    if last_updated:
                        # Convert date to datetime for age calculation
                        if col_type == "date":
                            last_updated = datetime.combine(
                                last_updated, datetime.min.time(), tzinfo=UTC
                            )

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
