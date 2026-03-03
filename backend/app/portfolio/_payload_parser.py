"""Parse raw payload dicts from data sources into PriceData objects."""

from __future__ import annotations

import json

from ..logging_config import get_logger
from .models import PriceData

logger = get_logger(__name__)

_NULL_STRINGS = {"null", "n/a", "none", ""}


def _safe_float(val: object) -> float | None:
    if val is None:
        return None
    if isinstance(val, str) and val.strip().lower() in _NULL_STRINGS:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val: object) -> int | None:
    if val is None:
        return None
    if isinstance(val, str) and val.strip().lower() in _NULL_STRINGS:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def parse_payload_row(row: dict) -> PriceData:
    """Convert a single DataFrame row from MultiSourceFetcher into a PriceData.

    The row is expected to have: symbol, source, payload (JSON string or dict).
    If the price is missing or zero a PriceData with error is returned.

    Args:
        row: A named dict from a Polars DataFrame row

    Returns:
        PriceData instance (may have error set if price is invalid)
    """
    symbol = row.get("symbol")
    if not symbol:
        raise ValueError(f"Missing required field 'symbol' in row: {row}")
    source: str = row.get("source", "unknown")
    payload = row.get("payload", {})

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON payload for symbol '{symbol}': {exc}"
            ) from exc

    price = payload.get("price", 0.0)
    sector = payload.get("sector")
    beta = payload.get("beta")
    volatility = payload.get("volatility")
    bid = payload.get("bid")
    ask = payload.get("ask")
    bid_size = payload.get("bidSize") or payload.get("bid_size")
    ask_size = payload.get("askSize") or payload.get("ask_size")

    if price and price > 0:
        logger.info(
            "price_fetch_success",
            symbol=symbol,
            price=float(price),
            source=source,
            has_beta=beta is not None,
            has_volatility=volatility is not None,
            has_sector=sector is not None,
        )
        return PriceData(
            symbol=symbol,
            price=float(price),
            beta=_safe_float(beta),
            volatility=_safe_float(volatility),
            sector=sector,
            bid=_safe_float(bid),
            ask=_safe_float(ask),
            bid_size=_safe_int(bid_size),
            ask_size=_safe_int(ask_size),
            source=source,
        )

    error_msg = "No price data available"
    logger.warning("price_fetch_no_data", symbol=symbol, error=error_msg, source=source)
    return PriceData(symbol=symbol, price=0.0, source=source, error=error_msg)


def build_all_sources_failed_entry(
    symbol: str,
    errors_by_source: dict[str, list[str]],
) -> PriceData:
    """Build a failed PriceData entry when all sources have failed.

    Args:
        symbol: The symbol that could not be fetched
        errors_by_source: Mapping of source name to list of error strings

    Returns:
        PriceData with error message set
    """
    error_details = " | ".join(
        [f"{src}: {', '.join(errs)}" for src, errs in errors_by_source.items()]
    )
    error_msg = (
        f"All sources failed: {error_details}" if error_details else "All sources failed"
    )
    logger.warning("price_fetch_all_sources_failed", symbol=symbol, errors=errors_by_source)
    return PriceData(symbol=symbol, price=0.0, source="multi_source", error=error_msg)
