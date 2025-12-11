"""Market movers data source with failover.

Primary: yahooquery (Yahoo Finance Screener)
Fallback: Alpaca Markets Data API

Both sources provide day gainers/losers, but yahooquery has better
quality filtering (excludes penny stocks, warrants).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from typing import TYPE_CHECKING, Any

import requests

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
    rvol = None
    if volume and avg_volume and avg_volume > 0:
        rvol = round(volume / avg_volume, 2)

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


def fetch_from_yahooquery(count: int = 10) -> MarketMoversResult | None:
    """Fetch market movers from Yahoo Finance via yahooquery.

    Args:
        count: Number of gainers/losers to fetch (max 25)

    Returns:
        MarketMoversResult or None if fetch fails
    """
    try:
        from yahooquery import Screener  # type: ignore[import-not-found]  # noqa: PLC0415

        s = Screener()
        data = s.get_screeners(["day_gainers", "day_losers", "most_actives"], count=count)

        gainers: list[MarketMover] = []
        losers: list[MarketMover] = []
        most_active: list[MarketMover] = []

        # Parse gainers
        if "day_gainers" in data and "quotes" in data["day_gainers"]:
            for q in data["day_gainers"]["quotes"][:count]:
                gainers.append(_parse_quote(q))

        # Parse losers
        if "day_losers" in data and "quotes" in data["day_losers"]:
            for q in data["day_losers"]["quotes"][:count]:
                losers.append(_parse_quote(q))

        # Parse most active (top volume)
        if "most_actives" in data and "quotes" in data["most_actives"]:
            for q in data["most_actives"]["quotes"][:count]:
                most_active.append(_parse_quote(q))

        # Calculate top RVOL from all unique stocks across screens
        all_stocks: dict[str, MarketMover] = {}
        for mover in gainers + losers + most_active:
            if mover.symbol and mover.symbol not in all_stocks:
                all_stocks[mover.symbol] = mover

        # Sort by RVOL descending, filter out None
        top_rvol = sorted(
            [m for m in all_stocks.values() if m.rvol is not None],
            key=lambda x: x.rvol or 0,
            reverse=True,
        )[:count]

        from datetime import datetime  # noqa: PLC0415

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
        # Get Alpaca credentials
        with storage.connection() as conn:
            result = conn.execute(
                "SELECT field, value FROM source_credentials WHERE source_id = 'alpaca'"
            )
            creds = {row[0]: row[1] for row in result.fetchall()}

        key_id = creds.get("key_id") or creds.get("api_key")
        secret = creds.get("secret_key")

        if not key_id or not secret:
            logger.warning("alpaca_credentials_missing")
            return None

        headers: dict[str, str] = {
            "APCA-API-KEY-ID": str(key_id),
            "APCA-API-SECRET-KEY": str(secret),
        }

        # Fetch more than needed to allow for filtering
        url = f"https://data.alpaca.markets/v1beta1/screener/stocks/movers?top={count * 3}"
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code != 200:
            logger.warning("alpaca_movers_failed", status=resp.status_code)
            return None

        data = resp.json()

        gainers: list[MarketMover] = []
        losers: list[MarketMover] = []

        # Parse and filter gainers (exclude penny stocks and warrants)
        for g in data.get("gainers", []):
            if len(gainers) >= count:
                break
            price = float(g.get("price", 0))
            symbol = g.get("symbol", "")
            # Filter: price > min_price, no warrants (W suffix), no rights (RT suffix)
            if price >= min_price and not symbol.endswith("W") and not symbol.endswith(".RT"):
                gainers.append(
                    MarketMover(
                        symbol=symbol,
                        name=None,  # Alpaca doesn't provide names
                        price=price,
                        change_pct=float(g.get("percent_change", 0)),
                        volume=None,  # Alpaca movers don't include volume
                        market_cap=None,
                    )
                )

        # Parse and filter losers
        for lo in data.get("losers", []):
            if len(losers) >= count:
                break
            price = float(lo.get("price", 0))
            symbol = lo.get("symbol", "")
            if price >= min_price and not symbol.endswith("W") and not symbol.endswith(".RT"):
                losers.append(
                    MarketMover(
                        symbol=symbol,
                        name=None,
                        price=price,
                        change_pct=float(lo.get("percent_change", 0)),
                        volume=None,
                        market_cap=None,
                    )
                )

        logger.info(
            "alpaca_movers_fetched",
            gainers_count=len(gainers),
            losers_count=len(losers),
        )

        return MarketMoversResult(
            gainers=gainers,
            losers=losers,
            most_active=[],  # Alpaca doesn't provide this
            top_rvol=[],  # Alpaca doesn't provide avg volume for RVOL
            source="alpaca",
            last_updated=data.get("last_updated"),
        )

    except Exception as e:
        logger.warning("alpaca_movers_failed", error=str(e))
        return None


def fetch_market_movers(storage: PortfolioStorage, count: int = 10) -> MarketMoversResult:
    """Fetch market movers with automatic failover.

    Tries yahooquery first (better quality), falls back to Alpaca.

    Args:
        storage: Storage instance for Alpaca credentials
        count: Number of gainers/losers to fetch

    Returns:
        MarketMoversResult (may have empty lists if all sources fail)
    """
    # Try yahooquery first (better quality)
    result = fetch_from_yahooquery(count)
    if result and (result.gainers or result.losers):
        return result

    # Fallback to Alpaca
    logger.info("market_movers_fallback_to_alpaca")
    result = fetch_from_alpaca(storage, count)
    if result and (result.gainers or result.losers):
        return result

    # All sources failed
    logger.warning("market_movers_all_sources_failed")
    return MarketMoversResult(
        gainers=[],
        losers=[],
        most_active=[],
        top_rvol=[],
        source="none",
        last_updated=None,
    )
