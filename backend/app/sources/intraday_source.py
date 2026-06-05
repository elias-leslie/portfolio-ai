"""Current-session intraday bar fetchers for the watchlist scanner.

``day_bars`` only carries completed daily sessions, so the scanner's "Today" (D)
trendline had no honest data. These fetchers pull the *current* trading day's
5-minute bars, normalized to one schema, with a tested fallback chain:

1. yfinance   — primary. Free, no key, one batched download for all symbols,
                returns the live current session (~10-15 min delayed).
2. twelvedata — fallback. Per-symbol, also current-session, but free tier is
                rate-limited (8/min, 800/day) so it only fills symbols yfinance
                missed.
3. polygon    — last resort. Its delayed feed serves only the *prior* completed
                session, so the line may be a day stale — still better than a
                blank "Today" when the live sources are down.

All three are normalized to: symbol, ts (UTC), session_date (US/Eastern trading
date), open/high/low/close, volume, source. Bars are filtered to the regular
session (09:30-16:00 ET) so the three feeds are directly comparable.
"""

from __future__ import annotations

import datetime as dt
import math
import os
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pandas as pd
import polars as pl
import yfinance as yf

from ..logging_config import get_logger
from .yfinance_fetchers import _managed_yf_session, _to_yf_symbol

logger = get_logger(__name__)

_EASTERN = ZoneInfo("America/New_York")
_REGULAR_OPEN = dt.time(9, 30)
_REGULAR_CLOSE = dt.time(16, 0)
INTRADAY_INTERVAL = "5min"

_INTRADAY_SCHEMA = {
    "symbol": pl.Utf8,
    "ts": pl.Datetime(time_unit="us", time_zone="UTC"),
    "session_date": pl.Date,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Int64,
    "source": pl.Utf8,
}


def _f(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if not math.isnan(parsed) else None  # drop NaN


def _make_record(
    symbol: str,
    ts_utc: dt.datetime,
    open_: Any,
    high: Any,
    low: Any,
    close: Any,
    volume: Any,
    source: str,
) -> dict[str, Any] | None:
    """Build one normalized intraday row, keeping only regular-session bars."""
    close_f = _f(close)
    if close_f is None or close_f <= 0:
        return None
    if ts_utc.tzinfo is None:
        ts_utc = ts_utc.replace(tzinfo=dt.UTC)
    ts_utc = ts_utc.astimezone(dt.UTC)
    east = ts_utc.astimezone(_EASTERN)
    if not (_REGULAR_OPEN <= east.time() < _REGULAR_CLOSE):
        return None
    vol = _f(volume)
    return {
        "symbol": symbol.upper(),
        "ts": ts_utc,
        "session_date": east.date(),
        "open": _f(open_),
        "high": _f(high),
        "low": _f(low),
        "close": close_f,
        "volume": int(vol) if vol is not None else None,
        "source": source,
    }


def _frame(records: list[dict[str, Any]]) -> pl.DataFrame | None:
    if not records:
        return None
    return pl.DataFrame(records, schema=_INTRADAY_SCHEMA)


def fetch_intraday_yfinance(symbols: list[str]) -> pl.DataFrame | None:
    """Primary: one batched yfinance download of the current session's 5-min bars."""
    if not symbols:
        return None
    yf_to_canon = {_to_yf_symbol(s): s.upper() for s in symbols}
    records: list[dict[str, Any]] = []
    try:
        with _managed_yf_session() as session:
            data = yf.download(
                tickers=list(yf_to_canon),
                period="1d",
                interval="5m",
                group_by="ticker",
                threads=True,
                progress=False,
                prepost=False,
                auto_adjust=False,
                session=session,
            )
    except Exception as exc:  # source failure must not break ingest
        logger.warning("intraday_yfinance_failed", error=str(exc), error_type=type(exc).__name__)
        return None

    if data is None or data.empty:
        return None
    multi = isinstance(data.columns, pd.MultiIndex)
    for yf_sym, canon in yf_to_canon.items():
        try:
            if multi:
                if yf_sym not in data.columns.get_level_values(0):
                    continue
                sub = data[yf_sym]
            else:
                sub = data
            sub = sub.dropna(subset=["Close"])
            for idx, row in sub.iterrows():
                ts_utc = idx.tz_convert("UTC").to_pydatetime() if idx.tzinfo else idx.to_pydatetime()
                rec = _make_record(
                    canon, ts_utc, row.get("Open"), row.get("High"),
                    row.get("Low"), row.get("Close"), row.get("Volume"), "yfinance",
                )
                if rec:
                    records.append(rec)
        except Exception as exc:  # per-symbol failure must not break the batch
            logger.debug("intraday_yfinance_symbol_failed", symbol=canon, error=str(exc))
    logger.info("intraday_yfinance_fetched", symbols=len(yf_to_canon), bars=len(records))
    return _frame(records)


def fetch_intraday_twelvedata(symbols: list[str]) -> pl.DataFrame | None:
    """Fallback: per-symbol TwelveData time_series (current session, rate-limited)."""
    key = os.getenv("TWELVEDATA_API_KEY")
    if not key or not symbols:
        return None
    records: list[dict[str, Any]] = []
    for symbol in symbols:
        try:
            resp = httpx.get(
                "https://api.twelvedata.com/time_series",
                params={
                    "symbol": _to_yf_symbol(symbol),
                    "interval": INTRADAY_INTERVAL,
                    "outputsize": 100,
                    "timezone": "UTC",
                    "apikey": key,
                },
                timeout=20,
            )
            payload = resp.json()
            if payload.get("status") == "error":
                logger.debug(
                    "intraday_twelvedata_symbol_error",
                    symbol=symbol,
                    message=str(payload.get("message"))[:160],
                )
                continue
            for value in payload.get("values", []) or []:
                ts = dt.datetime.fromisoformat(str(value["datetime"])).replace(tzinfo=dt.UTC)
                rec = _make_record(
                    symbol, ts, value.get("open"), value.get("high"),
                    value.get("low"), value.get("close"), value.get("volume"), "twelvedata",
                )
                if rec:
                    records.append(rec)
        except Exception as exc:  # per-symbol failure must not break the batch
            logger.debug("intraday_twelvedata_symbol_failed", symbol=symbol, error=str(exc))
    if records:
        logger.info("intraday_twelvedata_fetched", symbols=len(symbols), bars=len(records))
    return _frame(records)


def fetch_intraday_polygon(symbols: list[str]) -> pl.DataFrame | None:
    """Last resort: per-symbol Polygon 5-min aggregates (delayed; prior session)."""
    key = os.getenv("POLYGON_API_KEY")
    if not key or not symbols:
        return None
    today = dt.datetime.now(dt.UTC).date()
    frm = (today - dt.timedelta(days=5)).isoformat()
    to = today.isoformat()
    records: list[dict[str, Any]] = []
    for symbol in symbols:
        try:
            url = f"https://api.polygon.io/v2/aggs/ticker/{_to_yf_symbol(symbol)}/range/5/minute/{frm}/{to}"
            resp = httpx.get(
                url,
                params={"adjusted": "true", "sort": "asc", "limit": 50000, "apiKey": key},
                timeout=20,
            )
            if resp.status_code != 200:
                logger.debug("intraday_polygon_symbol_http", symbol=symbol, status=resp.status_code)
                continue
            for bar in resp.json().get("results", []) or []:
                ts = dt.datetime.fromtimestamp(bar["t"] / 1000, dt.UTC)
                rec = _make_record(
                    symbol, ts, bar.get("o"), bar.get("h"),
                    bar.get("l"), bar.get("c"), bar.get("v"), "polygon",
                )
                if rec:
                    records.append(rec)
        except Exception as exc:  # per-symbol failure must not break the batch
            logger.debug("intraday_polygon_symbol_failed", symbol=symbol, error=str(exc))
    if records:
        logger.info("intraday_polygon_fetched", symbols=len(symbols), bars=len(records))
    return _frame(records)


def _missing_symbols(frame: pl.DataFrame | None, symbols: list[str]) -> list[str]:
    if frame is None or frame.is_empty():
        return list(symbols)
    have = {str(s).upper() for s in frame["symbol"].unique().to_list()}
    return [s for s in symbols if s.upper() not in have]


def fetch_intraday_with_fallback(
    symbols: list[str],
) -> tuple[pl.DataFrame | None, dict[str, int]]:
    """Fetch current-session intraday bars, filling gaps down the source chain.

    yfinance covers the whole watchlist in one call; any symbol it misses is
    retried against TwelveData, then Polygon. Returns the combined frame plus a
    per-source bar count for observability.
    """
    normalized = list(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
    if not normalized:
        return None, {}

    frames: list[pl.DataFrame] = []
    counts: dict[str, int] = {}
    remaining = normalized

    for name, fetcher in (
        ("yfinance", fetch_intraday_yfinance),
        ("twelvedata", fetch_intraday_twelvedata),
        ("polygon", fetch_intraday_polygon),
    ):
        if not remaining:
            break
        frame = fetcher(remaining)
        if frame is not None and not frame.is_empty():
            frames.append(frame)
            counts[name] = len(frame)
            remaining = _missing_symbols(frame, remaining)

    if remaining:
        logger.warning("intraday_symbols_unresolved", symbols=remaining, count=len(remaining))
    if not frames:
        return None, counts
    return pl.concat(frames, how="vertical"), counts
