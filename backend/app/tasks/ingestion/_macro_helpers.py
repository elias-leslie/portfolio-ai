"""Private helper functions for macro indicator ingestion.

This module contains internal helpers used by fundamental_ingestion.py.
Not part of the public API — import from fundamental_ingestion instead.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.logging_config import get_logger
from app.sources.fred import FREDSource
from app.storage import PortfolioStorage

from ._fundamental_helpers import to_python

logger = get_logger(__name__)

YIELD_CURVE_FIELD_COUNT = 5  # yield_3m, yield_2y, yield_5y, yield_10y, yield_30y
_YIELD_CURVE_INDICATORS = {
    "YIELD_3M": "yield_3m",
    "YIELD_2Y": "yield_2y",
    "YIELD_5Y": "yield_5y",
    "YIELD_10Y": "yield_10y",
    "YIELD_30Y": "yield_30y",
}
_MACRO_INDICATOR_GROUPS = {
    "fetch_inflation_data": ("CPI", "CORE_CPI", "PCE", "BREAKEVEN_5Y", "BREAKEVEN_10Y"),
    "fetch_fed_funds_data": ("FEDFUNDS", "EFFR"),
}


def insert_yield_curve(
    storage: PortfolioStorage, data: dict[str, Any], as_of_date: date
) -> None:
    """Insert yield curve data."""
    query = """
        INSERT INTO yield_curve (
            observation_date, yield_3m, yield_2y, yield_5y, yield_10y, yield_30y,
            spread_10y_2y, spread_10y_3m, source
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'fred')
        ON CONFLICT (observation_date)
        DO UPDATE SET
            yield_3m = EXCLUDED.yield_3m,
            yield_2y = EXCLUDED.yield_2y,
            yield_5y = EXCLUDED.yield_5y,
            yield_10y = EXCLUDED.yield_10y,
            yield_30y = EXCLUDED.yield_30y,
            spread_10y_2y = EXCLUDED.spread_10y_2y,
            spread_10y_3m = EXCLUDED.spread_10y_3m
    """
    storage.execute(
        query,
        [
            datetime.combine(as_of_date, datetime.min.time()),
            to_python(data.get("yield_3m")),
            to_python(data.get("yield_2y")),
            to_python(data.get("yield_5y")),
            to_python(data.get("yield_10y")),
            to_python(data.get("yield_30y")),
            to_python(data.get("spread_10y_2y")),
            to_python(data.get("spread_10y_3m")),
        ],
    )


def insert_macro_indicator(
    storage: PortfolioStorage,
    indicator: str,
    value: float,
    as_of_date: date,
) -> None:
    """Insert a single macro indicator."""
    series_id = FREDSource.INDICATORS.get(indicator)
    query = """
        INSERT INTO macro_indicators (indicator_name, series_id, observation_date, value, source)
        VALUES ($1, $2, $3, $4, 'fred')
        ON CONFLICT (indicator_name, observation_date)
        DO UPDATE SET value = EXCLUDED.value
    """
    storage.execute(
        query,
        [
            indicator,
            series_id,
            datetime.combine(as_of_date, datetime.min.time()),
            to_python(value),
        ],
    )


def fetch_and_store_yield_curve(
    storage: PortfolioStorage, fred: FREDSource, today: date, stats: dict[str, Any]
) -> None:
    """Fetch yield curve from FRED and persist; update stats in place."""
    try:
        yield_data: dict[str, float | None] = {}
        observation_dates: list[date] = []
        for indicator, field_name in _YIELD_CURVE_INDICATORS.items():
            latest = fred.get_latest_value(indicator)
            if latest is None:
                yield_data[field_name] = None
                continue
            observation_date, value = latest
            observation_dates.append(observation_date)
            yield_data[field_name] = value

        if observation_dates:
            y10 = yield_data.get("yield_10y")
            y2 = yield_data.get("yield_2y")
            y3m = yield_data.get("yield_3m")
            yield_data["spread_10y_2y"] = (
                y10 - y2 if isinstance(y10, float) and isinstance(y2, float) else None
            )
            yield_data["spread_10y_3m"] = (
                y10 - y3m if isinstance(y10, float) and isinstance(y3m, float) else None
            )
            insert_yield_curve(storage, yield_data, min(observation_dates))
            stats["yield_curve_updated"] = True
            stats["indicators_inserted"] += YIELD_CURVE_FIELD_COUNT
    except Exception as e:
        stats["errors"].append({"indicator": "yield_curve", "error": str(e)})
        logger.error("yield_curve_fetch_failed", error=str(e), exc_info=True)


def fetch_and_store_indicators(
    storage: PortfolioStorage,
    fred: FREDSource,
    today: date,
    stats: dict[str, Any],
    fetch_fn_name: str,
    stat_key: str,
) -> None:
    """Fetch a named FRED indicator set and persist each value; update stats in place."""
    try:
        indicator_names = _MACRO_INDICATOR_GROUPS.get(fetch_fn_name)
        if indicator_names is not None:
            inserted = 0
            for indicator in indicator_names:
                latest = fred.get_latest_value(indicator)
                if latest is None:
                    continue
                observation_date, value = latest
                insert_macro_indicator(storage, indicator, value, observation_date)
                inserted += 1
            if inserted:
                stats["indicators_inserted"] += inserted
                stats[stat_key] = True
            return

        fetch_fn = getattr(fred, fetch_fn_name, None)
        if fetch_fn is None:
            raise AttributeError(f"FREDSource has no method '{fetch_fn_name}'")
        data = fetch_fn()
        if data:
            for indicator, value in data.items():
                if value is not None:
                    insert_macro_indicator(storage, indicator.upper(), value, today)
                    stats["indicators_inserted"] += 1
            stats[stat_key] = True
    except Exception as e:
        stats["errors"].append({"indicator": stat_key, "error": str(e)})
        logger.error("indicator_fetch_failed", indicator=stat_key, error=str(e), exc_info=True)
