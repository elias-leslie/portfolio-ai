"""Helper functions and data classes for market movers source.

Internal module — import via market_movers_source instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import requests

from app.constants import SHORT_HTTP_TIMEOUT
from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)


@dataclass
class MarketMover:
    """Single market mover entry."""

    symbol: str
    name: str | None
    price: float
    change_pct: float
    volume: int | None
    market_cap: int | None
    avg_volume: int | None = None  # For RVOL calculation
    rvol: float | None = None  # Relative volume (volume / avg_volume)
    sector: str | None = None  # e.g., "Technology", "Healthcare"


@dataclass
class MarketMoversResult:
    """Result from market movers fetch."""

    gainers: list[MarketMover]
    losers: list[MarketMover]
    most_active: list[MarketMover]  # Top volume
    top_rvol: list[MarketMover]  # Highest relative volume
    source: str  # "yahooquery" or "alpaca"
    last_updated: str | None


def _parse_quote(q: dict[str, Any]) -> MarketMover:
    """Parse a Yahoo Finance quote into a MarketMover."""
    volume = int(q.get("regularMarketVolume", 0)) if q.get("regularMarketVolume") else None
    avg_volume = (
        int(q.get("averageDailyVolume3Month", 0)) if q.get("averageDailyVolume3Month") else None
    )
    rvol = round(volume / avg_volume, 2) if volume and avg_volume and avg_volume > 0 else None
    return MarketMover(
        symbol=q.get("symbol", ""),
        name=q.get("shortName") or q.get("longName"),
        price=float(q.get("regularMarketPrice", 0)),
        change_pct=float(q.get("regularMarketChangePercent", 0)),
        volume=volume,
        market_cap=int(q.get("marketCap", 0)) if q.get("marketCap") else None,
        avg_volume=avg_volume,
        rvol=rvol,
    )


def _enrich_sectors(all_stocks: dict[str, MarketMover]) -> None:
    """Batch-fetch sector data and attach to mover objects in-place."""
    symbols = list(all_stocks.keys())
    if not symbols:
        return
    try:
        from yahooquery import Ticker  # noqa: PLC0415

        profiles = Ticker(symbols).asset_profile
        if not isinstance(profiles, dict):
            return
        for sym, mover in all_stocks.items():
            if sym in profiles and isinstance(profiles[sym], dict):
                mover.sector = profiles[sym].get("sector")
    except Exception as e:
        logger.warning("sector_fetch_failed", error=str(e))


def _parse_alpaca_mover(raw: dict[str, Any], min_price: float) -> MarketMover | None:
    """Parse and filter a single Alpaca mover entry; returns None if filtered out."""
    price = float(raw.get("price", 0))
    symbol = raw.get("symbol", "")
    if price < min_price or symbol.endswith("W") or symbol.endswith(".RT"):
        return None
    return MarketMover(
        symbol=symbol,
        name=None,
        price=price,
        change_pct=float(raw.get("percent_change", 0)),
        volume=None,
        market_cap=None,
    )


def fetch_from_yahooquery(count: int = 10) -> MarketMoversResult | None:
    """Fetch market movers from Yahoo Finance via yahooquery.

    Args:
        count: Number of gainers/losers to fetch (max 25)

    Returns:
        MarketMoversResult or None if fetch fails
    """
    try:
        from yahooquery import Screener  # noqa: PLC0415

        data = Screener().get_screeners(["day_gainers", "day_losers", "most_actives"], count=count)
        gainers = [_parse_quote(q) for q in data.get("day_gainers", {}).get("quotes", [])[:count]]
        losers = [_parse_quote(q) for q in data.get("day_losers", {}).get("quotes", [])[:count]]
        most_active = [
            _parse_quote(q) for q in data.get("most_actives", {}).get("quotes", [])[:count]
        ]

        all_stocks: dict[str, MarketMover] = {}
        for mover in gainers + losers + most_active:
            if mover.symbol and mover.symbol not in all_stocks:
                all_stocks[mover.symbol] = mover

        _enrich_sectors(all_stocks)

        top_rvol = sorted(
            [m for m in all_stocks.values() if m.rvol is not None],
            key=lambda x: x.rvol or 0,
            reverse=True,
        )[:count]

        logger.info(
            "yahooquery_movers_fetched",
            gainers_count=len(gainers),
            losers_count=len(losers),
            most_active_count=len(most_active),
            top_rvol_count=len(top_rvol),
        )
        return MarketMoversResult(
            gainers=gainers,
            losers=losers,
            most_active=most_active,
            top_rvol=top_rvol,
            source="yahooquery",
            last_updated=datetime.now(UTC).isoformat(),
        )
    except Exception as e:
        logger.warning("yahooquery_movers_failed", error=str(e))
        return None


def fetch_from_alpaca(
    storage: PortfolioStorage, count: int = 10, min_price: float = 5.0
) -> MarketMoversResult | None:
    """Fetch market movers from Alpaca Markets API.

    Args:
        storage: Storage instance for credentials
        count: Number of gainers/losers to fetch
        min_price: Minimum price filter to exclude penny stocks

    Returns:
        MarketMoversResult or None if fetch fails
    """
    try:
        with storage.connection() as conn:
            rows = conn.execute(
                "SELECT field, value FROM source_credentials WHERE source_id = 'alpaca'"
            ).fetchall()
        creds = {row[0]: row[1] for row in rows}
        key_id = creds.get("key_id") or creds.get("api_key")
        secret = creds.get("secret_key")

        if not key_id or not secret:
            logger.warning("alpaca_credentials_missing")
            return None

        headers: dict[str, str] = {
            "APCA-API-KEY-ID": str(key_id),
            "APCA-API-SECRET-KEY": str(secret),
        }
        url = f"https://data.alpaca.markets/v1beta1/screener/stocks/movers?top={count * 3}"
        resp = requests.get(url, headers=headers, timeout=SHORT_HTTP_TIMEOUT)

        if resp.status_code != 200:
            logger.warning("alpaca_movers_failed", status=resp.status_code)
            return None

        data = resp.json()
        gainers: list[MarketMover] = []
        losers: list[MarketMover] = []

        for g in data.get("gainers", []):
            if len(gainers) >= count:
                break
            mover = _parse_alpaca_mover(g, min_price)
            if mover:
                gainers.append(mover)

        for lo in data.get("losers", []):
            if len(losers) >= count:
                break
            mover = _parse_alpaca_mover(lo, min_price)
            if mover:
                losers.append(mover)

        logger.info("alpaca_movers_fetched", gainers_count=len(gainers), losers_count=len(losers))
        return MarketMoversResult(
            gainers=gainers,
            losers=losers,
            most_active=[],
            top_rvol=[],
            source="alpaca",
            last_updated=data.get("last_updated"),
        )
    except Exception as e:
        logger.warning("alpaca_movers_failed", error=str(e))
        return None
