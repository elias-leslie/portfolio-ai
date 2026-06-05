"""Batched price-trend summaries for the watchlist scanner."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from app.storage import PortfolioStorage

# Trader-natural price-trend windows for the scanner sparklines, each ending now:
#   D  Today        — the current session's intraday closes (intraday_bars).
#   W  Past week    — the last 5 daily closes (one trading week) from day_bars.
#   Q  Past quarter — the last 13 ISO-week closes from day_bars.
#   Y  Past year    — the last 52 ISO-week closes from day_bars.
# D is built separately (it has a live-session source plus a daily fallback); the
# rest are rolling windows. Each rolling entry is (key, label, source, target):
# "daily" reads day_bars closes directly, "weekly" the last close of each ISO
# week. W/Q/Y all end today, so a young symbol just yields a shorter,
# partial-flagged series — never faked or back-padded.
_ROLLING_WINDOWS: tuple[tuple[str, str, str, int], ...] = (
    ("W", "1W", "daily", 5),
    ("Q", "1Q", "weekly", 13),
    ("Y", "1Y", "weekly", 52),
)

# Last close of each ISO week is read back this far (largest weekly window + holiday buffer).
_WEEKLY_LOOKBACK_DAYS = 372
# Trailing daily closes read in one batch: serves the W window (last 5) and the
# D fallback (last 2 when the live session has no bars yet).
_DAILY_LOOKBACK_POINTS = 5
# A full regular session is ~78 five-minute bars; cap the "Today" line here so a
# stray backfill can't bloat the payload. The intraday read already returns only
# the latest session, so this is normally a no-op.
_INTRADAY_MAX_POINTS = 96
# Below this fraction of a window's target point count, the series is flagged partial
# (drives the "young symbol" marker in the UI). The D window opts out — a session
# still forming is normal, not an incomplete history.
_PARTIAL_FRACTION = 0.85


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


def _intraday_series_rows(storage: PortfolioStorage, normalized_symbols: list[str]) -> Any:
    """Current-session 5-minute closes per symbol, oldest-first, one batched read.

    Reads only each symbol's most recent ``session_date`` and orders by ``ts`` so
    the "Today" line traces the live session left-to-right. ``ts`` is aliased to
    ``bar_date`` so the row flows through the shared ``_series_by_symbol``; its
    ISO form keeps the time component, which the UI shows in the intraday tooltip.
    """
    values_clause = ",".join("(?)" for _ in normalized_symbols)
    return storage.query(
        f"""
        WITH requested(symbol) AS (
            VALUES {values_clause}
        )
        SELECT requested.symbol AS symbol, bars.ts AS bar_date, bars.close AS close
        FROM requested
        JOIN LATERAL (
            SELECT ts, close
            FROM intraday_bars
            WHERE symbol = requested.symbol
              AND session_date = (
                  SELECT MAX(session_date)
                  FROM intraday_bars
                  WHERE symbol = requested.symbol
              )
              AND close IS NOT NULL
              AND close > 0
            ORDER BY ts ASC
        ) bars ON TRUE
        ORDER BY requested.symbol, bars.ts ASC
        """,
        normalized_symbols,
    )


def _daily_series_rows(storage: PortfolioStorage, normalized_symbols: list[str]) -> Any:
    """Last ``_DAILY_LOOKBACK_POINTS`` daily closes per symbol, oldest-first, one batched read."""
    values_clause = ",".join("(?)" for _ in normalized_symbols)
    return storage.query(
        f"""
        WITH requested(symbol) AS (
            VALUES {values_clause}
        )
        SELECT requested.symbol AS symbol, bars.date AS bar_date, bars.close AS close
        FROM requested
        JOIN LATERAL (
            SELECT date, close
            FROM day_bars
            WHERE symbol = requested.symbol
              AND close IS NOT NULL
              AND close > 0
            ORDER BY date DESC
            LIMIT {_DAILY_LOOKBACK_POINTS}
        ) bars ON TRUE
        ORDER BY requested.symbol, bars.date ASC
        """,
        normalized_symbols,
    )


def _weekly_series_rows(storage: PortfolioStorage, normalized_symbols: list[str]) -> Any:
    """Last close of each ISO week per symbol over the trailing year, oldest-first, one batched read."""
    values_clause = ",".join("(?)" for _ in normalized_symbols)
    return storage.query(
        f"""
        WITH requested(symbol) AS (
            VALUES {values_clause}
        )
        SELECT symbol, bar_date, close
        FROM (
            SELECT DISTINCT ON (requested.symbol, date_trunc('week', bars.date))
                   requested.symbol AS symbol,
                   bars.date AS bar_date,
                   bars.close AS close
            FROM requested
            JOIN day_bars bars ON bars.symbol = requested.symbol
            WHERE bars.close IS NOT NULL
              AND bars.close > 0
              AND bars.date >= CURRENT_DATE - INTERVAL '{_WEEKLY_LOOKBACK_DAYS} days'
            ORDER BY requested.symbol, date_trunc('week', bars.date), bars.date DESC
        ) weekly
        ORDER BY symbol, bar_date ASC
        """,
        normalized_symbols,
    )


def _series_by_symbol(
    rows: Any, normalized_symbols: list[str]
) -> dict[str, list[tuple[Any, float]]]:
    out: dict[str, list[tuple[Any, float]]] = {symbol: [] for symbol in normalized_symbols}
    if rows.is_empty():
        return out
    for row in rows.iter_rows(named=True):
        close = _to_float(row.get("close"))
        if close is None:
            continue
        out.setdefault(str(row["symbol"]).upper(), []).append((row.get("bar_date"), close))
    return out


def _trend_for_window(
    points: list[tuple[Any, float]],
    key: str,
    label: str,
    target: int,
    *,
    end_source: str = "day_bars",
    flag_partial: bool = True,
) -> dict[str, Any]:
    window_points = points[-target:] if points else []
    series = [{"date": _to_iso_date(bar_date), "close": close} for bar_date, close in window_points]
    count = len(window_points)
    base = {"key": key, "label": label, "end_source": end_source, "series": series, "point_count": count}
    if count == 0:
        return {
            **base,
            "return_pct": None,
            "start_close": None,
            "end_close": None,
            "start_date": None,
            "end_date": None,
            "status": "missing",
            "partial": False,
        }

    start_date, start_close = window_points[0]
    end_date, end_close = window_points[-1]
    if count < 2 or not start_close:
        return {
            **base,
            "return_pct": None,
            "start_close": start_close,
            "end_close": end_close,
            "start_date": _to_iso_date(start_date),
            "end_date": _to_iso_date(end_date),
            "status": "insufficient_history",
            "partial": flag_partial,
        }

    return {
        **base,
        "return_pct": ((end_close - start_close) / start_close) * 100,
        "start_close": start_close,
        "end_close": end_close,
        "start_date": _to_iso_date(start_date),
        "end_date": _to_iso_date(end_date),
        "status": "available",
        "partial": flag_partial and count < math.ceil(target * _PARTIAL_FRACTION),
    }


def _today_trend(
    intraday_points: list[tuple[Any, float]],
    daily_points: list[tuple[Any, float]],
) -> dict[str, Any]:
    """Build the "Today" (D) trend from the live session, falling back to daily.

    Prefer the current session's intraday closes; when the session has not drawn a
    line yet (pre-open, or a symbol the intraday feeds missed) fall back to the
    last two daily closes so D still shows a recent move. Either way D is never
    flagged partial/young — a session still forming is normal, not short history.
    """
    if len(intraday_points) >= 2:
        return _trend_for_window(
            intraday_points,
            "D",
            "Today",
            _INTRADAY_MAX_POINTS,
            end_source="intraday_bars",
            flag_partial=False,
        )
    return _trend_for_window(
        daily_points,
        "D",
        "Today",
        2,
        end_source="day_bars",
        flag_partial=False,
    )


def build_price_trend_map(
    storage: PortfolioStorage,
    symbols: list[str],
) -> dict[str, list[dict[str, Any]]]:
    """Return D/W/Q/Y close-series trend summaries for symbols in three batched reads.

    The scanner is not a realtime chart. D ("Today") carries the current session's
    intraday closes from ``intraday_bars`` (falling back to the last two daily
    closes when the session is empty); W/Q/Y carry a downsampled close series from
    cached ``day_bars`` (the trailing trading week, then last-close-of-week over a
    quarter and a year) plus the window return. W/Q/Y end today, so a young symbol
    just yields a shorter series flagged ``partial`` rather than a broken or
    back-padded line. D is never flagged partial — a forming session is expected.
    """
    normalized_symbols = list(
        dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip())
    )
    if not normalized_symbols:
        return {}

    intraday_by_symbol = _series_by_symbol(
        _intraday_series_rows(storage, normalized_symbols), normalized_symbols
    )
    daily_by_symbol = _series_by_symbol(
        _daily_series_rows(storage, normalized_symbols), normalized_symbols
    )
    weekly_by_symbol = _series_by_symbol(
        _weekly_series_rows(storage, normalized_symbols), normalized_symbols
    )

    result: dict[str, list[dict[str, Any]]] = {}
    for symbol in normalized_symbols:
        trends: list[dict[str, Any]] = [
            _today_trend(intraday_by_symbol.get(symbol, []), daily_by_symbol.get(symbol, []))
        ]
        for key, label, source, target in _ROLLING_WINDOWS:
            points = (
                daily_by_symbol.get(symbol, [])
                if source == "daily"
                else weekly_by_symbol.get(symbol, [])
            )
            trends.append(_trend_for_window(points, key, label, target))
        result[symbol] = trends

    return result


def build_score_series_map(
    storage: PortfolioStorage,
    item_ids: list[str],
    *,
    window_days: int = 30,
) -> dict[str, dict[str, Any]]:
    """Return a daily-aggregated overall-score series per watchlist item_id in one batched read.

    Mirrors the price-sparkline shape so the Score column can render the same
    interactive trendline. Score history only exists from when a symbol started
    being scored, so the series is naturally short for new items.
    """
    normalized_ids = list(
        dict.fromkeys(str(item_id).strip() for item_id in item_ids if str(item_id).strip())
    )
    if not normalized_ids:
        return {}

    values_clause = ",".join("(?)" for _ in normalized_ids)
    rows = storage.query(
        f"""
        WITH requested(item_id) AS (
            VALUES {values_clause}
        )
        SELECT s.item_id AS item_id,
               (s.fetched_at AT TIME ZONE 'UTC')::date AS day,
               AVG(s.overall_score) AS overall
        FROM watchlist_snapshots_v s
        JOIN requested ON requested.item_id = s.item_id
        WHERE s.fetched_at >= (CURRENT_DATE - INTERVAL '{int(window_days)} days')
          AND s.overall_score IS NOT NULL
        GROUP BY s.item_id, (s.fetched_at AT TIME ZONE 'UTC')::date
        ORDER BY s.item_id, day ASC
        """,
        normalized_ids,
    )

    series_by_item: dict[str, list[dict[str, Any]]] = {item_id: [] for item_id in normalized_ids}
    if not rows.is_empty():
        for row in rows.iter_rows(named=True):
            try:
                value = float(row.get("overall"))
            except (TypeError, ValueError):
                continue
            if not math.isfinite(value):
                continue
            series_by_item.setdefault(str(row["item_id"]), []).append(
                {"date": _to_iso_date(row.get("day")), "value": value}
            )

    result: dict[str, dict[str, Any]] = {}
    for item_id in normalized_ids:
        series = series_by_item.get(item_id, [])
        result[item_id] = {
            "series": series,
            "current": series[-1]["value"] if series else None,
            "point_count": len(series),
            "status": "available" if len(series) >= 2 else ("insufficient_history" if series else "missing"),
        }
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
