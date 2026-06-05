"""Batched price-trend summaries for the watchlist scanner."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from app.storage import PortfolioStorage

_TREND_WINDOWS: tuple[tuple[str, str, int], ...] = (
    ("D", "1D", 1),
    ("W", "5D", 5),
    ("M", "1M", 21),
    ("Q", "3M", 63),
)


def _to_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed > 0 else None


def _to_iso_date(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _quote_end_price(quote: dict[str, Any] | None) -> tuple[float | None, str | None, str]:
    if not quote:
        return None, None, "daily_close"
    price = _to_float(quote.get("price"))
    cached_at = quote.get("cached_at")
    as_of = None
    if isinstance(cached_at, str):
        as_of = cached_at
    elif isinstance(cached_at, datetime):
        as_of = cached_at.astimezone(UTC).isoformat()
    return price, as_of, "quote" if price is not None else "daily_close"


def build_price_trend_map(
    storage: PortfolioStorage,
    symbols: list[str],
    quote_map: dict[str, dict[str, Any] | None],
) -> dict[str, list[dict[str, Any]]]:
    """Return W/M/Q close-based trend summaries for symbols in one DB read.

    The scanner is not a realtime chart. These trends use cached daily bars plus
    the current cached quote when available, so they are useful for triage
    without blocking page load on market-data vendors.
    """
    normalized_symbols = list(
        dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip())
    )
    if not normalized_symbols:
        return {}

    values_clause = ",".join("(?)" for _ in normalized_symbols)
    ranked_rows = storage.query(
        f"""
        WITH requested(symbol) AS (
            VALUES {values_clause}
        )
        SELECT requested.symbol, bars.date, bars.close, bars.vwap, bars.rn
        FROM requested
        JOIN LATERAL (
            SELECT
                date,
                close,
                vwap,
                ROW_NUMBER() OVER (ORDER BY date DESC) AS rn
            FROM (
                SELECT date, close, vwap
                FROM day_bars
                WHERE symbol = requested.symbol
                  AND close IS NOT NULL
                  AND close > 0
                ORDER BY date DESC
                LIMIT 64
            ) limited
        ) bars ON TRUE
        ORDER BY requested.symbol, bars.rn
        """,
        normalized_symbols,
    )

    rows_by_symbol: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in normalized_symbols}
    if not ranked_rows.is_empty():
        for row in ranked_rows.iter_rows(named=True):
            rows_by_symbol.setdefault(str(row["symbol"]).upper(), []).append(row)

    result: dict[str, list[dict[str, Any]]] = {}
    for symbol in normalized_symbols:
        rows = rows_by_symbol.get(symbol, [])
        latest = rows[0] if rows else None
        quote_end, quote_as_of, end_source = _quote_end_price(quote_map.get(symbol))
        latest_close = _to_float(latest.get("close")) if latest else None
        end_price = quote_end or latest_close
        end_date = quote_as_of or (_to_iso_date(latest.get("date")) if latest else None)
        if end_price is None:
            result[symbol] = [
                {
                    "key": key,
                    "label": label,
                    "return_pct": None,
                    "start_close": None,
                    "end_close": None,
                    "start_date": None,
                    "end_date": end_date,
                    "end_source": end_source,
                    "status": "missing",
                }
                for key, label, _window in _TREND_WINDOWS
            ]
            continue

        trends: list[dict[str, Any]] = []
        for key, label, window in _TREND_WINDOWS:
            start_row = rows[window] if len(rows) > window else None
            start_close = _to_float(start_row.get("close")) if start_row else None
            start_date = _to_iso_date(start_row.get("date")) if start_row else None
            return_pct = (
                ((end_price - start_close) / start_close) * 100
                if start_close is not None
                else None
            )
            trends.append(
                {
                    "key": key,
                    "label": label,
                    "return_pct": return_pct,
                    "start_close": start_close,
                    "end_close": end_price,
                    "start_date": start_date,
                    "end_date": end_date,
                    "end_source": end_source,
                    "status": "available" if return_pct is not None else "insufficient_history",
                }
            )
        result[symbol] = trends

    return result


def build_vwap_signal_map(
    storage: PortfolioStorage,
    symbols: list[str],
    quote_map: dict[str, dict[str, Any] | None],
) -> dict[str, dict[str, Any]]:
    """Return latest-session VWAP context for symbols in one DB read."""
    normalized_symbols = list(
        dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip())
    )
    if not normalized_symbols:
        return {}

    values_clause = ",".join("(?)" for _ in normalized_symbols)
    rows = storage.query(
        f"""
        WITH requested(symbol) AS (
            VALUES {values_clause}
        )
        SELECT
            requested.symbol,
            latest_close.date AS close_date,
            latest_close.close,
            latest_vwap.date AS vwap_date,
            latest_vwap.vwap
        FROM requested
        LEFT JOIN LATERAL (
            SELECT date, close
            FROM day_bars
            WHERE symbol = requested.symbol
              AND close IS NOT NULL
              AND close > 0
            ORDER BY date DESC
            LIMIT 1
        ) latest_close ON TRUE
        LEFT JOIN LATERAL (
            SELECT date, vwap
            FROM day_bars
            WHERE symbol = requested.symbol
              AND vwap IS NOT NULL
              AND vwap::text <> 'NaN'
              AND vwap > 0
            ORDER BY date DESC
            LIMIT 1
        ) latest_vwap ON TRUE
        ORDER BY requested.symbol
        """,
        normalized_symbols,
    )

    latest_by_symbol: dict[str, dict[str, Any]] = {}
    if not rows.is_empty():
        latest_by_symbol = {
            str(row["symbol"]).upper(): row for row in rows.iter_rows(named=True)
        }

    result: dict[str, dict[str, Any]] = {}
    for symbol in normalized_symbols:
        row = latest_by_symbol.get(symbol)
        quote_price, quote_as_of, end_source = _quote_end_price(quote_map.get(symbol))
        close = _to_float(row.get("close")) if row else None
        vwap = _to_float(row.get("vwap")) if row else None
        close_date = row.get("close_date") if row else None
        vwap_date = row.get("vwap_date") if row else None
        price = quote_price or close
        distance_pct = (
            ((price - vwap) / vwap) * 100
            if price is not None and vwap is not None
            else None
        )
        status = "missing"
        if distance_pct is not None:
            status = "available" if close_date == vwap_date else "stale"
        result[symbol] = {
            "status": status,
            "vwap": vwap,
            "price": price,
            "close": close,
            "distance_pct": distance_pct,
            "as_of_date": _to_iso_date(vwap_date) if row else None,
            "close_as_of_date": _to_iso_date(close_date) if row else None,
            "price_as_of": quote_as_of,
            "price_source": end_source,
            "source": "day_bars",
        }

    return result
