"""Capability checking logic for gap detection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...logging_config import get_logger
from .types import CapabilityRequirement

if TYPE_CHECKING:
    from ...storage.connection import ConnectionManager

logger = get_logger(__name__)


class CapabilityChecker:
    """Checks system capabilities and data availability."""

    def __init__(self, connection_mgr: ConnectionManager) -> None:
        """Initialize capability checker.

        Args:
            connection_mgr: ConnectionManager instance for database access
        """
        self.conn_mgr = connection_mgr
        self._capabilities_cache: dict[str, Any] | None = None

    def get_current_capabilities(self) -> dict[str, Any]:
        """Query current system capabilities from capability registry.

        Returns:
            Dict mapping table names to capability metadata
        """
        if self._capabilities_cache is not None:
            return self._capabilities_cache

        logger.info("fetching_current_capabilities")

        capabilities = {}

        with self.conn_mgr.connection() as conn:
            # Fetch database capabilities
            tables_result = conn.execute(
                """
                SELECT
                    table_name,
                    category,
                    row_count,
                    total_columns,
                    columns,
                    completeness_pct,
                    date_range_start,
                    date_range_end,
                    days_since_update,
                    freshness_status
                FROM db_capabilities
                ORDER BY table_name
                """
            ).fetchall()

            for row in tables_result:
                # Unpack tuple result (order matches SELECT columns)
                (
                    table_name,
                    category,
                    row_count,
                    total_columns,
                    columns,
                    completeness_pct,
                    date_range_start,
                    date_range_end,
                    days_since_update,
                    freshness_status,
                ) = row

                capabilities[table_name] = {
                    "category": category,
                    "row_count": row_count,
                    "total_columns": total_columns,
                    "columns": columns,
                    "completeness_pct": completeness_pct,
                    "date_range_start": date_range_start,
                    "date_range_end": date_range_end,
                    "days_since_update": days_since_update,
                    "freshness_status": freshness_status,
                }

        self._capabilities_cache = capabilities

        logger.info(
            "capabilities_fetched",
            total_tables=len(capabilities),
        )

        return capabilities

    def check_capability_available(
        self,
        requirement: CapabilityRequirement,
        capabilities: dict[str, Any],
    ) -> tuple[bool, str]:
        """Check if a required capability is available in the system.

        Args:
            requirement: Capability requirement from trading_requirements.yaml
            capabilities: Current system capabilities

        Returns:
            Tuple of (is_available: bool, reason: str)
        """
        required_tables = requirement.get("tables", [])

        if not required_tables:
            # No specific tables required (might be calculated metric)
            return (False, "no_tables_specified")

        # Check if all required tables exist and have data
        missing_tables = []
        empty_tables = []
        stale_tables = []

        for table_name in required_tables:
            if table_name not in capabilities:
                missing_tables.append(table_name)
                continue

            table_cap = capabilities[table_name]

            # Check if table has data
            if table_cap["row_count"] == 0:
                empty_tables.append(table_name)
                continue

            # Check freshness
            if table_cap["freshness_status"] == "stale":
                stale_tables.append(table_name)

        if missing_tables:
            return (
                False,
                f"missing_tables: {', '.join(missing_tables)}",
            )

        if empty_tables:
            return (
                False,
                f"empty_tables: {', '.join(empty_tables)}",
            )

        if stale_tables:
            return (
                False,
                f"stale_tables: {', '.join(stale_tables)}",
            )

        # All required tables exist, have data, and are fresh
        return (True, "available")

    def check_ticker_data_availability(self, ticker: str) -> dict[str, Any]:
        """Check what data exists for a specific ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dict mapping table names to availability status
        """
        availability: dict[str, Any] = {}

        # Check key tables for ticker-specific data
        tables_to_check = [
            ("day_bars", "SELECT COUNT(*) FROM day_bars WHERE ticker = %s", [ticker]),
            (
                "technical_indicators",
                "SELECT COUNT(*) FROM technical_indicators WHERE ticker = %s",
                [ticker],
            ),
            (
                "fundamentals",
                "SELECT COUNT(*) FROM fundamentals WHERE ticker = %s",
                [ticker],
            ),
            (
                "news_cache",
                "SELECT COUNT(*) FROM news_cache WHERE ticker = %s",
                [ticker],
            ),
            (
                "analyst_ratings",
                "SELECT COUNT(*) FROM analyst_ratings WHERE ticker = %s",
                [ticker],
            ),
        ]

        # Check each table individually to avoid transaction rollback issues
        for table_name, query, params in tables_to_check:
            try:
                with self.conn_mgr.connection() as conn:
                    result = conn.execute(query, params).fetchone()
                    row_count = result[0] if result else 0
                    availability[table_name] = {
                        "exists": True,
                        "has_data": row_count > 0,
                        "row_count": row_count,
                    }
            except Exception as e:
                logger.warning(
                    f"Failed to check {table_name} for {ticker}: {e}",
                    table=table_name,
                    ticker=ticker,
                )
                availability[table_name] = {
                    "exists": False,
                    "has_data": False,
                    "row_count": 0,
                }

        return availability

    def ticker_has_capability(
        self,
        ticker: str,
        requirement: CapabilityRequirement,
        ticker_data_availability: dict[str, Any],
    ) -> bool:
        """Check if a ticker has data for a specific capability.

        Args:
            ticker: Stock ticker symbol
            requirement: Capability requirement from trading_requirements.yaml
            ticker_data_availability: Pre-fetched data availability for ticker

        Returns:
            True if ticker has data for this capability
        """
        required_tables = requirement.get("tables", [])

        if not required_tables:
            # No specific tables required - assume available
            return True

        # Check if ticker has data in ALL required tables
        for table_name in required_tables:
            table_avail = ticker_data_availability.get(table_name, {})
            if not table_avail.get("has_data", False):
                return False

        return True

    def clear_cache(self) -> None:
        """Clear cached capabilities (force refresh on next query)."""
        self._capabilities_cache = None
