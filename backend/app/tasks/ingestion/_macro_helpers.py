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
FRED_INDICATORS_BY_FETCH_FN: dict[str, tuple[str, ...]] = {
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
    observation_date: date,
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
            datetime.combine(observation_date, datetime.min.time()),
            to_python(value),
        ],
    )


def _coerce_indicator_point(raw: Any, fallback_date: date) -> tuple[date, float] | None:
    if raw is None:
        return None
    if isinstance(raw, tuple) and len(raw) == 2:
        raw_date, raw_value = raw
    elif isinstance(raw, dict):
        raw_date = raw.get("observation_date") or raw.get("date")
        raw_value = raw.get("value")
    else:
        raw_date = fallback_date
        raw_value = raw

    try:
        if isinstance(raw_date, datetime):
            observation_date = raw_date.date()
        elif isinstance(raw_date, date):
            observation_date = raw_date
        elif isinstance(raw_date, str):
            observation_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        else:
            observation_date = fallback_date
        return observation_date, float(raw_value)
    except (TypeError, ValueError):
        return None


def _fetch_indicator_points(
    fred: FREDSource,
    fetch_fn_name: str,
    fallback_date: date,
) -> dict[str, tuple[date, float] | None]:
    indicators = FRED_INDICATORS_BY_FETCH_FN.get(fetch_fn_name)
    if indicators and hasattr(fred, "get_latest_value"):
        return {indicator: fred.get_latest_value(indicator) for indicator in indicators}

    fetch_fn = getattr(fred, fetch_fn_name, None)
    if fetch_fn is None:
        raise AttributeError(f"FREDSource has no method '{fetch_fn_name}'")
    data = fetch_fn()
    if not data:
        return {}
    return {
        str(indicator).upper(): _coerce_indicator_point(value, fallback_date)
        for indicator, value in data.items()
    }


def fetch_and_store_yield_curve(
    storage: PortfolioStorage, fred: FREDSource, today: date, stats: dict[str, Any]
) -> None:
    """Fetch yield curve from FRED and persist; update stats in place."""
    try:
        yield_data = fred.fetch_yield_curve()
        if yield_data:
            insert_yield_curve(storage, yield_data, today)
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
        data = _fetch_indicator_points(fred, fetch_fn_name, today)
        if data:
            for indicator, point in data.items():
                if point is not None:
                    observation_date, value = point
                    insert_macro_indicator(storage, indicator.upper(), value, observation_date)
                    stats["indicators_inserted"] += 1
            stats[stat_key] = True
    except Exception as e:
        stats["errors"].append({"indicator": stat_key, "error": str(e)})
        logger.error("indicator_fetch_failed", indicator=stat_key, error=str(e), exc_info=True)
