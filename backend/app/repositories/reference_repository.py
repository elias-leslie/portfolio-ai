"""Repository layer for reference data database operations.

Handles all database queries for reference cache, valuation metrics,
financial health scores, and risk metrics.

Pattern: Repository handles data access, tasks handle business logic.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from app.storage import PortfolioStorage


class ReferenceRepository:
    """Database access layer for reference data operations."""

    def __init__(self, storage: PortfolioStorage):
        """Initialize repository with storage instance.

        Args:
            storage: PortfolioStorage instance for database access
        """
        self.storage = storage

    def get_latest_cache_entry_date(self, symbol: str, source: str) -> dt.date | None:
        """Get the as_of_date of the most recent cache entry for symbol/source.

        Args:
            symbol: Stock symbol
            source: Data source (e.g., "fundamentals", "yfinance")

        Returns:
            as_of_date of most recent entry, or None if not found
        """
        with self.storage.connection() as conn:
            result = conn.execute(
                """
                SELECT as_of_date
                FROM reference_cache
                WHERE symbol = %s AND source = %s
                ORDER BY as_of_date DESC
                LIMIT 1
                """,
                [symbol, source],
            ).fetchone()

            return cast(dt.date, result[0]) if result else None

    def get_cache_entries_with_payloads(
        self,
    ) -> list[tuple[str, str, Any]]:
        """Get all cache entries with non-null payloads.

        Returns:
            List of (symbol, source, payload) tuples ordered by symbol, source, date desc
        """
        with self.storage.connection() as conn:
            results = conn.execute(
                """
                SELECT symbol, source, payload
                FROM reference_cache
                WHERE payload IS NOT NULL
                ORDER BY symbol, source, as_of_date DESC
                """
            ).fetchall()

            return [(str(r[0]), str(r[1]), r[2]) for r in results]

    def update_reference_cache_valuation(
        self,
        symbol: str,
        source: str,
        as_of_date: dt.date,
        metrics: dict[str, float | None],
    ) -> None:
        """Update valuation metrics columns in reference_cache.

        Args:
            symbol: Stock symbol
            source: Data source
            as_of_date: Date of the cache entry
            metrics: Dict with pe_ratio_trailing, pe_ratio_forward, ps_ratio,
                     pb_ratio, peg_ratio, dividend_yield, payout_ratio
        """
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE reference_cache
                SET pe_ratio_trailing = %s, pe_ratio_forward = %s, ps_ratio = %s,
                    pb_ratio = %s, peg_ratio = %s, dividend_yield = %s, payout_ratio = %s
                WHERE symbol = %s AND source = %s AND as_of_date = %s
                """,
                [
                    metrics.get("pe_ratio_trailing"),
                    metrics.get("pe_ratio_forward"),
                    metrics.get("ps_ratio"),
                    metrics.get("pb_ratio"),
                    metrics.get("peg_ratio"),
                    metrics.get("dividend_yield"),
                    metrics.get("payout_ratio"),
                    symbol,
                    source,
                    as_of_date.isoformat(),
                ],
            )
            conn.commit()

    def upsert_valuation_metrics(
        self,
        symbol: str,
        as_of_date: dt.date,
        metrics: dict[str, float | None],
    ) -> None:
        """Upsert valuation metrics to dedicated table.

        Args:
            symbol: Stock symbol
            as_of_date: Date for the metrics record
            metrics: Dict with pe_ratio_trailing, pe_ratio_forward, ps_ratio,
                     pb_ratio, peg_ratio, dividend_yield, payout_ratio
        """
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO valuation_metrics (
                    symbol, as_of_date,
                    pe_ratio_trailing, pe_ratio_forward, ps_ratio,
                    pb_ratio, peg_ratio, dividend_yield, payout_ratio
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, as_of_date) DO UPDATE SET
                    pe_ratio_trailing = EXCLUDED.pe_ratio_trailing,
                    pe_ratio_forward = EXCLUDED.pe_ratio_forward,
                    ps_ratio = EXCLUDED.ps_ratio,
                    pb_ratio = EXCLUDED.pb_ratio,
                    peg_ratio = EXCLUDED.peg_ratio,
                    dividend_yield = EXCLUDED.dividend_yield,
                    payout_ratio = EXCLUDED.payout_ratio,
                    updated_at = NOW()
                """,
                [
                    symbol,
                    as_of_date.isoformat(),
                    metrics.get("pe_ratio_trailing"),
                    metrics.get("pe_ratio_forward"),
                    metrics.get("ps_ratio"),
                    metrics.get("pb_ratio"),
                    metrics.get("peg_ratio"),
                    metrics.get("dividend_yield"),
                    metrics.get("payout_ratio"),
                ],
            )
            conn.commit()

    def upsert_financial_health_scores(
        self,
        symbol: str,
        as_of_date: dt.date,
        f_score: int | None,
        f_score_components: str | None,
        z_score: float | None,
        z_score_zone: str | None,
    ) -> None:
        """Upsert financial health scores (F-Score, Z-Score).

        Args:
            symbol: Stock symbol
            as_of_date: Date for the scores
            f_score: Piotroski F-Score (0-9)
            f_score_components: JSON string of score components
            z_score: Altman Z-Score
            z_score_zone: Zone classification (safe/grey/distress)
        """
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO financial_health_scores (
                    symbol, as_of_date,
                    f_score, f_score_components, z_score, z_score_zone
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, as_of_date) DO UPDATE SET
                    f_score = EXCLUDED.f_score,
                    f_score_components = EXCLUDED.f_score_components,
                    z_score = EXCLUDED.z_score,
                    z_score_zone = EXCLUDED.z_score_zone,
                    updated_at = NOW()
                """,
                [
                    symbol,
                    as_of_date.isoformat(),
                    f_score,
                    f_score_components,
                    z_score,
                    z_score_zone,
                ],
            )
            conn.commit()

    def update_reference_cache_health_scores(
        self,
        symbol: str,
        f_score: int | None,
        f_score_components: str | None,
        z_score: float | None,
        z_score_zone: str | None,
    ) -> None:
        """Update health score columns in reference_cache for most recent entry.

        Args:
            symbol: Stock symbol
            f_score: Piotroski F-Score
            f_score_components: JSON string of score components
            z_score: Altman Z-Score
            z_score_zone: Zone classification
        """
        with self.storage.connection() as conn:
            conn.execute(
                """
                UPDATE reference_cache
                SET f_score = %s, f_score_components = %s,
                    z_score = %s, z_score_zone = %s
                WHERE symbol = %s
                  AND as_of_date = (
                      SELECT MAX(as_of_date) FROM reference_cache WHERE symbol = %s
                  )
                """,
                [f_score, f_score_components, z_score, z_score_zone, symbol, symbol],
            )
            conn.commit()

    def upsert_risk_metrics(
        self,
        symbol: str,
        as_of_date: dt.date,
        var_95: float | None,
        var_99: float | None,
        cvar_95: float | None,
        cvar_99: float | None,
        beta_90d: float | None,
        beta_1y: float | None,
        beta_2y: float | None,
        r_squared_1y: float | None,
        observations: int | None,
    ) -> None:
        """Upsert risk metrics (VaR, CVaR, betas).

        Args:
            symbol: Stock symbol
            as_of_date: Date for the metrics
            var_95: 95% Value at Risk
            var_99: 99% Value at Risk
            cvar_95: 95% Conditional VaR
            cvar_99: 99% Conditional VaR
            beta_90d: 90-day beta
            beta_1y: 1-year beta
            beta_2y: 2-year beta
            r_squared_1y: R-squared for 1-year regression
            observations: Number of observations used
        """
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO symbol_risk_metrics (
                    symbol, as_of_date,
                    var_95, var_99, cvar_95, cvar_99,
                    beta_90d, beta_1y, beta_2y, r_squared_1y,
                    observations
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, as_of_date)
                DO UPDATE SET
                    var_95 = EXCLUDED.var_95,
                    var_99 = EXCLUDED.var_99,
                    cvar_95 = EXCLUDED.cvar_95,
                    cvar_99 = EXCLUDED.cvar_99,
                    beta_90d = EXCLUDED.beta_90d,
                    beta_1y = EXCLUDED.beta_1y,
                    beta_2y = EXCLUDED.beta_2y,
                    r_squared_1y = EXCLUDED.r_squared_1y,
                    observations = EXCLUDED.observations
                """,
                [
                    symbol,
                    as_of_date.isoformat(),
                    var_95,
                    var_99,
                    cvar_95,
                    cvar_99,
                    beta_90d,
                    beta_1y,
                    beta_2y,
                    r_squared_1y,
                    observations,
                ],
            )
            conn.commit()

    def get_stale_symbols(self, days_threshold: int = 7) -> list[str]:
        """Get symbols needing reference data refresh.

        Identifies symbols from watchlist with:
        - No yfinance data in cache, OR
        - yfinance data older than threshold days

        Args:
            days_threshold: Number of days after which data is considered stale

        Returns:
            List of symbols needing fresh data
        """
        with self.storage.connection() as conn:
            result = conn.execute(
                """
                SELECT DISTINCT wi.symbol
                FROM watchlist_items wi
                LEFT JOIN (
                    SELECT symbol, MAX(as_of_date) as latest_date
                    FROM reference_cache
                    WHERE source = 'yfinance'
                    GROUP BY symbol
                ) rc ON wi.symbol = rc.symbol
                WHERE rc.symbol IS NULL
                   OR rc.latest_date < CURRENT_DATE - (%s * INTERVAL '1 day')
                """,
                [days_threshold],
            )
            return [str(row[0]) for row in result.fetchall()]

    def upsert_reference_cache(
        self,
        symbol: str,
        as_of_date: dt.date,
        payload: str,
        source: str,
    ) -> None:
        """Upsert a reference cache entry.

        Args:
            symbol: Stock symbol
            as_of_date: Date for the cache entry
            payload: JSON payload string
            source: Data source identifier (e.g., "yfinance", "alphavantage")
        """
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO reference_cache (symbol, as_of_date, payload, source)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (symbol, as_of_date, source)
                DO UPDATE SET payload = EXCLUDED.payload
                """,
                [symbol, as_of_date.isoformat(), payload, source],
            )
            conn.commit()

    def upsert_dual_write_metrics(
        self,
        symbol: str,
        as_of_date: dt.date,
        base_table_update_sql: str,
        base_table_params: list[Any],
        metrics_table: str,
        metrics_columns: list[str],
        metrics_values: list[Any],
        conflict_keys: list[str],
    ) -> None:
        """Write metrics to both reference_cache and a dedicated metrics table.

        This pattern is used for valuation metrics, financial health scores, etc.
        where we want both the cached payload + structured metrics columns AND
        a dedicated historical table for efficient queries.

        Args:
            symbol: Stock symbol
            as_of_date: Date for the metrics record
            base_table_update_sql: SQL to update reference_cache
            base_table_params: Parameters for base table update
            metrics_table: Name of dedicated metrics table
            metrics_columns: Column names for metrics table (excluding symbol, as_of_date)
            metrics_values: Values for metrics columns
            conflict_keys: Columns for ON CONFLICT clause
        """
        with self.storage.connection() as conn:
            # Update reference_cache (base table)
            conn.execute(base_table_update_sql, base_table_params)

            # Build metrics table INSERT with ON CONFLICT
            all_columns = ["symbol", "as_of_date", *metrics_columns]
            placeholders = ", ".join(["%s"] * len(all_columns))
            update_set = ", ".join(f"{col} = EXCLUDED.{col}" for col in metrics_columns)
            update_set += ", updated_at = NOW()"
            conflict_clause = ", ".join(conflict_keys)

            insert_sql = f"""
                INSERT INTO {metrics_table} ({", ".join(all_columns)})
                VALUES ({placeholders})
                ON CONFLICT ({conflict_clause}) DO UPDATE SET {update_set}
            """
            conn.execute(insert_sql, [symbol, as_of_date.isoformat(), *metrics_values])
            conn.commit()
