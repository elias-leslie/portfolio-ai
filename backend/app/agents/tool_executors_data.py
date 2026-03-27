"""Data tool executors for agent data fetching operations.

This module provides execution logic for data-fetching tools:
- get_news: Fetch news headlines
- get_economic_data: Fetch FRED economic indicators
- get_portfolio_data: Fetch portfolio positions and analytics
- get_price_data: Fetch price data with technical indicators
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.portfolio.analytics import PortfolioAnalytics
    from app.portfolio.manager import PortfolioManager
    from app.portfolio.price_fetcher import PriceDataFetcher
    from app.services import NewsService
    from app.sources.fred import FREDSource
    from app.storage.facade import PortfolioStorage

from app.logging_config import get_logger

logger = get_logger(__name__)

_NUM = (int, float)

# SQL query for fetching the latest technical indicators for a symbol
_INDICATORS_SQL = """
    SELECT
        rsi_14, macd, macd_signal, macd_histogram,
        bb_upper, bb_middle, bb_lower,
        sma_20, sma_50, sma_200,
        ema_20, ema_50, ema_200,
        atr_14, stoch_k, stoch_d,
        date
    FROM technical_indicators
    WHERE symbol = ?
    ORDER BY date DESC
    LIMIT 1
"""


def _rsi_label(rsi: float) -> str:
    if rsi < 30:
        return f"RSI={rsi:.1f} (oversold)"
    if rsi > 70:
        return f"RSI={rsi:.1f} (overbought)"
    return f"RSI={rsi:.1f} (neutral)"


def _bbands_label(price: float, upper: float, middle: float, lower: float) -> str:
    if price < lower:
        return "below lower Bollinger Band"
    if price > upper:
        return "above upper Bollinger Band"
    if price < middle:
        return "near lower Bollinger Band"
    return "near upper Bollinger Band"


def _sma200_label(price: float, sma_200: float) -> str:
    if price > sma_200:
        pct = (price - sma_200) / sma_200 * 100
        return f"{pct:.1f}% above 200-day SMA (uptrend)"
    pct = (sma_200 - price) / sma_200 * 100
    return f"{pct:.1f}% below 200-day SMA (downtrend)"


class DataTools:
    """Data fetching tool executors for agents."""

    def __init__(
        self,
        storage: PortfolioStorage,
        news_service: NewsService,
        fred_source: FREDSource,
        portfolio_mgr: PortfolioManager,
        analytics: PortfolioAnalytics,
        price_fetcher: PriceDataFetcher,
    ) -> None:
        self.storage = storage
        self.news_service = news_service
        self.fred_source = fred_source
        self.portfolio_mgr = portfolio_mgr
        self.analytics = analytics
        self.price_fetcher = price_fetcher

    def execute_get_news(self, query: str, max_results: int | None = None) -> dict[str, object]:
        """Execute get_news tool."""
        normalized_query = query.strip()
        pref_limit = self.news_service.refresh_max_articles_from_preferences()
        limit = max_results or pref_limit
        try:
            if normalized_query.lower() in {"market", "stock market", "overall"}:
                bundle = self.news_service.get_news_intelligence(None, max_articles=limit)
            elif normalized_query.isalpha() and len(normalized_query) <= 6:
                bundle = self.news_service.get_news_intelligence(
                    normalized_query.upper(), max_articles=limit
                )
            else:
                bundle = self.news_service.get_custom_news(normalized_query, max_articles=limit)

            return {
                "query": normalized_query,
                "symbol": bundle.symbol,
                "summary": bundle.summary.model_dump(),
                "articles": [article.model_dump() for article in bundle.articles[:limit]],
                "count": len(bundle.articles),
            }
        except Exception as exc:
            logger.error("agent_get_news_failed", query=query, error=str(exc), exc_info=True)
            raise

    def execute_get_economic_data(self, indicators: list[str]) -> dict[str, object]:
        """Execute get_economic_data tool."""
        data = self.fred_source.fetch_multiple(indicators)
        return {"indicators": data, "count": len(data)}

    def execute_get_portfolio_data(self) -> dict[str, object]:
        """Execute get_portfolio_data tool."""
        positions = self.portfolio_mgr.get_positions()
        if not positions:
            return {"positions": [], "analytics": None}

        symbols = list({p.symbol for p in positions})
        price_data = self.price_fetcher.fetch_price_data(symbols)
        analytics = self.analytics.calculate_full_analytics(positions, price_data)
        return {
            "positions": [p.model_dump(mode="json") for p in positions],
            "analytics": analytics.model_dump(mode="json"),
        }

    def execute_get_price_data(self, symbols: list[str]) -> dict[str, object]:
        """Execute get_price_data tool with technical indicators."""
        price_data = self.price_fetcher.fetch_price_data(symbols)
        enriched_prices = {}
        for sym, data in price_data.items():
            price_info = data.model_dump(mode="json")
            indicators = self._fetch_indicators(sym)
            if indicators:
                price_info["indicators"] = indicators
                price_info["analysis"] = self._format_indicator_analysis(
                    sym, data.price, indicators
                )
            enriched_prices[sym] = price_info
        return {"prices": enriched_prices, "count": len(price_data)}

    def _fetch_indicators(self, symbol: str) -> dict[str, object] | None:
        """Fetch latest technical indicators for a symbol from the database."""
        try:
            result = self.storage.query(_INDICATORS_SQL, [symbol.upper()])
            if result.is_empty():
                return None
            row = result.row(0, named=True)
            return {
                "rsi_14": row["rsi_14"],
                "macd": {
                    "macd": row["macd"],
                    "signal": row["macd_signal"],
                    "histogram": row["macd_histogram"],
                },
                "bbands": {
                    "upper": row["bb_upper"],
                    "middle": row["bb_middle"],
                    "lower": row["bb_lower"],
                },
                "sma_20": row["sma_20"],
                "sma_50": row["sma_50"],
                "sma_200": row["sma_200"],
                "ema_20": row["ema_20"],
                "ema_50": row["ema_50"],
                "ema_200": row["ema_200"],
                "atr_14": row["atr_14"],
                "stochastic": {"k": row["stoch_k"], "d": row["stoch_d"]},
                "date": str(row["date"]),
            }
        except Exception as e:
            logger.warning("indicators_fetch_failed", symbol=symbol, error=str(e), exc_info=True)
            return None

    def _format_indicator_analysis(
        self, symbol: str, current_price: float, indicators: dict[str, object]
    ) -> str:
        """Format technical indicators into human-readable analysis text."""
        parts = [f"{symbol} current price ${current_price:.2f}"]

        rsi = indicators.get("rsi_14")
        if isinstance(rsi, _NUM):
            parts.append(_rsi_label(rsi))

        macd_data = indicators.get("macd")
        macd_val = signal_val = None
        if isinstance(macd_data, dict):
            macd_val = macd_data.get("macd")
            signal_val = macd_data.get("signal")
            if isinstance(macd_val, _NUM) and isinstance(signal_val, _NUM):
                parts.append("MACD bullish cross" if macd_val > signal_val else "MACD bearish cross")

        bbands = indicators.get("bbands")
        if isinstance(bbands, dict):
            upper, middle, lower = bbands.get("upper"), bbands.get("middle"), bbands.get("lower")
            if isinstance(upper, _NUM) and isinstance(middle, _NUM) and isinstance(lower, _NUM):
                parts.append(_bbands_label(current_price, upper, middle, lower))

        sma_200 = indicators.get("sma_200")
        if isinstance(sma_200, _NUM):
            parts.append(_sma200_label(current_price, sma_200))

        stoch = indicators.get("stochastic")
        if isinstance(stoch, dict):
            stoch_k = stoch.get("k")
            if isinstance(stoch_k, _NUM):
                if stoch_k < 20:
                    parts.append(f"Stochastic={stoch_k:.1f} (oversold)")
                elif stoch_k > 80:
                    parts.append(f"Stochastic={stoch_k:.1f} (overbought)")

        signals = []
        if isinstance(rsi, _NUM):
            if rsi < 30:
                signals.append("potential buy signal")
            elif rsi > 70:
                signals.append("potential sell signal")
        if isinstance(macd_val, _NUM) and isinstance(signal_val, _NUM) and isinstance(rsi, _NUM):
            if macd_val > signal_val and rsi < 50:
                signals.append("bullish momentum building")
            elif macd_val < signal_val and rsi > 50:
                signals.append("bearish momentum building")

        if signals:
            parts.append(f"- {', '.join(signals)}")

        return ", ".join(parts)


__all__ = ["DataTools"]
