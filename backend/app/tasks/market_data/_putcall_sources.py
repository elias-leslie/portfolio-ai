"""Put/call ratio data source helpers.

Three data sources with fallback: yfinance (primary), Polygon, Finnhub.
"""

from __future__ import annotations

import os
from typing import Any

import requests
import yfinance as yf

from app.logging_config import get_logger

logger = get_logger(__name__)

PUTCALL_SYMBOLS = ["SPY", "QQQ", "IWM"]
PUTCALL_EXPIRATIONS = 5


def _fetch_symbol_volumes(symbol: str) -> tuple[float, float, dict[str, Any]] | None:
    """Fetch call/put volumes for one symbol. Returns (call_vol, put_vol, data) or None."""
    yf_obj = yf.Ticker(symbol)
    expirations = yf_obj.options[:PUTCALL_EXPIRATIONS]
    sym_call_vol = 0.0
    sym_put_vol = 0.0
    for exp in expirations:
        chain = yf_obj.option_chain(exp)
        sym_call_vol += chain.calls["volume"].fillna(0).sum()
        sym_put_vol += chain.puts["volume"].fillna(0).sum()
    if sym_call_vol == 0:
        return None
    ratio = float(sym_put_vol / sym_call_vol)
    logger.debug(
        "putcall_symbol_calculated",
        symbol=symbol,
        call_vol=int(sym_call_vol),
        put_vol=int(sym_put_vol),
        ratio=round(ratio, 2),
    )
    return sym_call_vol, sym_put_vol, {"call_volume": float(sym_call_vol), "put_volume": float(sym_put_vol), "ratio": ratio}


def _calculate_putcall_from_yfinance() -> dict[str, Any] | None:
    """Calculate put/call ratio from yfinance options chains (SPY+QQQ+IWM aggregate)."""
    try:
        total_call_vol = 0.0
        total_put_vol = 0.0
        symbol_data: dict[str, dict[str, float]] = {}
        for symbol in PUTCALL_SYMBOLS:
            try:
                result = _fetch_symbol_volumes(symbol)
                if result:
                    call_v, put_v, data = result
                    symbol_data[symbol] = data
                    total_call_vol += call_v
                    total_put_vol += put_v
            except Exception as e:
                logger.warning("putcall_symbol_failed", symbol=symbol, error=str(e))
        if total_call_vol == 0:
            logger.warning("yfinance_putcall_no_volume")
            return None
        return {
            "put_call_ratio": round(float(total_put_vol / total_call_vol), 4),
            "total_call_volume": int(total_call_vol),
            "total_put_volume": int(total_put_vol),
            "symbol_ratios": symbol_data,
            "source": "yfinance_options_chain",
            "symbols": PUTCALL_SYMBOLS,
            "expirations_per_symbol": PUTCALL_EXPIRATIONS,
        }
    except Exception as e:
        logger.warning("yfinance_putcall_failed", error=str(e))
        return None


def _calculate_putcall_from_polygon() -> dict[str, Any] | None:
    """Fallback: Calculate put/call ratio from Polygon options snapshot (SPY)."""
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        logger.debug("polygon_putcall_no_api_key")
        return None
    try:
        url = f"https://api.polygon.io/v3/snapshot/options/SPY?apiKey={api_key}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            logger.warning("polygon_putcall_no_data")
            return None
        total_call_vol = 0
        total_put_vol = 0
        for opt in results:
            volume = opt.get("day", {}).get("volume", 0)
            if opt.get("details", {}).get("contract_type") == "call":
                total_call_vol += volume
            elif opt.get("details", {}).get("contract_type") == "put":
                total_put_vol += volume
        if total_call_vol == 0:
            logger.warning("polygon_putcall_no_call_volume")
            return None
        ratio = float(total_put_vol / total_call_vol)
        logger.info("polygon_putcall_calculated", ratio=round(ratio, 2), call_vol=total_call_vol, put_vol=total_put_vol)
        return {
            "put_call_ratio": round(ratio, 4),
            "total_call_volume": total_call_vol,
            "total_put_volume": total_put_vol,
            "source": "polygon_options_snapshot",
            "symbols": ["SPY"],
        }
    except Exception as e:
        logger.warning("polygon_putcall_failed", error=str(e))
        return None


def _calculate_putcall_from_finnhub() -> dict[str, Any] | None:
    """Fallback: Calculate put/call ratio from Finnhub options chain (SPY)."""
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        logger.debug("finnhub_putcall_no_api_key")
        return None
    try:
        url = f"https://finnhub.io/api/v1/stock/option-chain?symbol=SPY&token={api_key}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        options_data = response.json().get("data", [])
        if not options_data:
            logger.warning("finnhub_putcall_no_data")
            return None
        total_call_vol = 0
        total_put_vol = 0
        for expiry in options_data:
            for opt in expiry.get("options", {}).get("CALL", []):
                total_call_vol += opt.get("volume", 0) or 0
            for opt in expiry.get("options", {}).get("PUT", []):
                total_put_vol += opt.get("volume", 0) or 0
        if total_call_vol == 0:
            logger.warning("finnhub_putcall_no_call_volume")
            return None
        ratio = float(total_put_vol / total_call_vol)
        logger.info("finnhub_putcall_calculated", ratio=round(ratio, 2), call_vol=total_call_vol, put_vol=total_put_vol)
        return {
            "put_call_ratio": round(ratio, 4),
            "total_call_volume": total_call_vol,
            "total_put_volume": total_put_vol,
            "source": "finnhub_options_chain",
            "symbols": ["SPY"],
        }
    except Exception as e:
        logger.warning("finnhub_putcall_failed", error=str(e))
        return None
