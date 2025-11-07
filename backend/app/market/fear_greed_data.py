"""Fear & Greed Index data fetching module.

Fetches all 5 signal inputs from various sources:
- VIX: FRED (VIXCLS)
- HY Spread: FRED (BAMLH0A0HYM2)
- Put/Call Ratio: CBOE CSV
- SPY Data: Local database (day_bars + technical_indicators)
"""

from __future__ import annotations

from datetime import date
from io import StringIO
from typing import Any

import httpx
import pandas as pd
import structlog

from ..sources.fred import FREDSource
from ..storage import PortfolioStorage

logger = structlog.get_logger(__name__)


class FearGreedDataFetcher:
    """Fetch Fear & Greed Index input signals from various sources."""

    CBOE_PUT_CALL_URL = (
        "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/equitypc.csv"
    )

    def __init__(self, storage: PortfolioStorage, fred_source: FREDSource | None = None) -> None:
        """Initialize data fetcher.

        Args:
            storage: Database storage instance
            fred_source: FRED API source (optional, creates default if None)
        """
        self.storage = storage
        self.fred_source = fred_source or FREDSource()
        self._put_call_cache: pd.DataFrame | None = None

    def fetch_vix(self, target_date: date) -> float | None:
        """Fetch VIX closing value for a specific date.

        Args:
            target_date: Date to fetch VIX for

        Returns:
            VIX closing value, or None if unavailable
        """
        try:
            data = self.fred_source.fetch_latest("VIX")
            if data and data.get("value"):
                logger.info(
                    "vix_fetched",
                    date=target_date,
                    value=data["value"],
                    source="FRED",
                )
                return float(data["value"])
            logger.warning("vix_not_available", date=target_date)
            return None
        except Exception as e:
            logger.error("vix_fetch_failed", date=target_date, error=str(e))
            return None

    def fetch_hy_spread(self, target_date: date) -> float | None:
        """Fetch High-Yield bond OAS spread for a specific date.

        Args:
            target_date: Date to fetch HY spread for

        Returns:
            HY spread in basis points, or None if unavailable
        """
        try:
            data = self.fred_source.fetch_latest("HY_SPREAD")
            if data and data.get("value"):
                logger.info(
                    "hy_spread_fetched",
                    date=target_date,
                    value=data["value"],
                    source="FRED",
                )
                return float(data["value"])
            logger.warning("hy_spread_not_available", date=target_date)
            return None
        except Exception as e:
            logger.error("hy_spread_fetch_failed", date=target_date, error=str(e))
            return None

    def fetch_put_call_ratio(self, target_date: date) -> float | None:
        """Fetch CBOE equity put/call ratio for a specific date.

        NOTE: CBOE CSV data feed was discontinued in 2019. This method will
        always return None for dates after 2019-12-31. The Fear & Greed Index
        calculation handles this gracefully by using 4 signals instead of 5,
        with the missing signal defaulting to neutral (50).

        TODO: Find alternative source for put/call ratio data:
        - Option 1: Use options chain data from Polygon/Finnhub if available
        - Option 2: Use proxy indicators (e.g., SKEW index, VIX term structure)
        - Option 3: Purchase CBOE data feed subscription

        Args:
            target_date: Date to fetch put/call ratio for

        Returns:
            Put/call ratio, or None if unavailable (always None for dates > 2019)
        """
        try:
            # OPTIMIZATION: Skip HTTP call entirely for dates after 2019
            # CBOE CSV was discontinued, so data won't exist anyway
            if target_date.year > 2019:
                logger.info(
                    "put_call_skipped_post2019",
                    date=target_date,
                    reason="CBOE data discontinued after 2019-12-31",
                )
                return None

            # Fetch CSV if not cached (only for pre-2020 dates)
            if self._put_call_cache is None:
                response = httpx.get(self.CBOE_PUT_CALL_URL, timeout=10.0)
                response.raise_for_status()

                # Parse CSV (skip first 2 header rows)
                csv_data = StringIO(response.text)
                df = pd.read_csv(csv_data, skiprows=2, parse_dates=["DATE"])
                self._put_call_cache = df
                logger.info("put_call_csv_cached", rows=len(df))

            # Find matching date
            df = self._put_call_cache
            df["DATE"] = pd.to_datetime(df["DATE"]).dt.date
            matching = df[df["DATE"] == target_date]

            if not matching.empty:
                # Column name is "P/C Ratio" in the CSV
                ratio = float(matching.iloc[0]["P/C Ratio"])
                logger.info(
                    "put_call_ratio_fetched",
                    date=target_date,
                    value=ratio,
                    source="CBOE",
                )
                return ratio

            logger.warning("put_call_ratio_not_found", date=target_date)
            return None

        except Exception as e:
            logger.error("put_call_ratio_fetch_failed", date=target_date, error=str(e))
            return None

    def fetch_spy_data(self, target_date: date) -> dict[str, Any] | None:
        """Fetch SPY price and technical indicators for a specific date.

        Args:
            target_date: Date to fetch SPY data for

        Returns:
            Dict with close, sma_200, and rsi_14, or None if data missing
        """
        try:
            with self.storage.connection() as conn:
                # Fetch SPY close price from day_bars
                result = conn.execute(
                    """
                    SELECT close
                    FROM day_bars
                    WHERE ticker = 'SPY'
                    AND date = %s
                    """,
                    (target_date,),
                )
                result = result.fetchone()
                if not result:
                    logger.warning("spy_price_not_found", date=target_date)
                    return None

                spy_close = float(result[0])

                # Fetch SPY technical indicators
                result = conn.execute(
                    """
                    SELECT sma_200, rsi_14
                    FROM technical_indicators
                    WHERE ticker = 'SPY'
                    AND date = %s
                    """,
                    (target_date,),
                )
                result = result.fetchone()
                if not result:
                    logger.warning("spy_indicators_not_found", date=target_date)
                    return None

                sma_200, rsi_14 = result
                if sma_200 is None or rsi_14 is None:
                    logger.warning(
                        "spy_indicators_incomplete",
                        date=target_date,
                        sma_200=sma_200,
                        rsi_14=rsi_14,
                    )
                    return None

                data = {
                    "close": spy_close,
                    "sma_200": float(sma_200),
                    "rsi_14": float(rsi_14),
                }
                logger.info("spy_data_fetched", date=target_date, data=data)
                return data

        except Exception as e:
            logger.error("spy_data_fetch_failed", date=target_date, error=str(e))
            return None

    def fetch_all_inputs(self, target_date: date) -> dict[str, Any]:
        """Fetch all Fear & Greed input signals for a specific date.

        Args:
            target_date: Date to fetch signals for

        Returns:
            Dict with all signal values and source_map
            Keys: vix_close, hy_spread, put_call_ratio, spy_close, spy_sma_200, rsi_14, source_map
        """
        source_map: dict[str, str] = {}
        result: dict[str, Any] = {"date": target_date, "source_map": source_map}

        # Fetch VIX
        vix = self.fetch_vix(target_date)
        if vix is not None:
            result["vix_close"] = vix
            source_map["vix"] = "FRED"

        # Fetch HY Spread
        hy_spread = self.fetch_hy_spread(target_date)
        if hy_spread is not None:
            result["hy_spread"] = hy_spread
            source_map["hy_spread"] = "FRED"

        # Fetch Put/Call Ratio
        put_call = self.fetch_put_call_ratio(target_date)
        if put_call is not None:
            result["put_call_ratio"] = put_call
            source_map["put_call"] = "CBOE"

        # Fetch SPY data
        spy_data = self.fetch_spy_data(target_date)
        if spy_data:
            result["spy_close"] = spy_data["close"]
            result["spy_sma_200"] = spy_data["sma_200"]
            result["rsi_14"] = spy_data["rsi_14"]
            source_map["spy"] = "database"

        # Log missing signals
        required_signals = ["vix_close", "hy_spread", "put_call_ratio", "spy_close"]
        missing = [s for s in required_signals if s not in result]
        if missing:
            logger.warning("missing_signals", date=target_date, missing=missing)

        logger.info(
            "all_inputs_fetched",
            date=target_date,
            signals_count=len([k for k in result if k not in ["date", "source_map"]]),
            source_map=source_map,
        )

        return result
