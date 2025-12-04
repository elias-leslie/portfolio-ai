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
        """Initialize data tools.

        Args:
            storage: PortfolioStorage instance
            news_service: NewsService instance
            fred_source: FREDSource instance
            portfolio_mgr: PortfolioManager instance
            analytics: PortfolioAnalytics instance
            price_fetcher: PriceDataFetcher instance
        """
        self.storage = storage
        self.news_service = news_service
        self.fred_source = fred_source
        self.portfolio_mgr = portfolio_mgr
        self.analytics = analytics
        self.price_fetcher = price_fetcher

    def execute_get_news(self, query: str, max_results: int | None = None) -> dict[str, object]:
        """Execute get_news tool.

        Args:
            query: News search query
            max_results: Maximum number of results to return

        Returns:
            Dictionary with query results
        """
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
            logger.error("agent_get_news_failed", query=query, error=str(exc))
            raise

    def execute_get_economic_data(self, indicators: list[str]) -> dict[str, object]:
        """Execute get_economic_data tool.

        Args:
            indicators: List of FRED indicator names

        Returns:
            Dictionary with indicator data
        """
        data = self.fred_source.fetch_multiple(indicators)
        return {"indicators": data, "count": len(data)}

    def execute_get_portfolio_data(self) -> dict[str, object]:
        """Execute get_portfolio_data tool.

        Returns:
            Dictionary with positions and analytics
        """
        positions = self.portfolio_mgr.get_positions()

        if not positions:
            return {"positions": [], "analytics": None}

        # Get price data for all symbols
        symbols = list({p.symbol for p in positions})
        price_data = self.price_fetcher.fetch_price_data(symbols)

        # Calculate analytics
        analytics = self.analytics.calculate_full_analytics(positions, price_data)

        return {
            "positions": [p.model_dump(mode="json") for p in positions],
            "analytics": analytics.model_dump(mode="json"),
        }

    def execute_get_price_data(self, symbols: list[str]) -> dict[str, object]:
        """Execute get_price_data tool with technical indicators.

        Fetches current price data and enriches it with technical indicators
        from the technical_indicators table. Returns formatted interpretations
        to help agents make informed trading decisions.

        Args:
            symbols: List of stock symbols

        Returns:
            Dictionary with enriched price data
        """
        price_data = self.price_fetcher.fetch_price_data(symbols)

        # Fetch technical indicators for each symbol
        enriched_prices = {}
        for sym, data in price_data.items():
            price_info = data.model_dump(mode="json")

            # Fetch latest technical indicators from database
            indicators = self._fetch_indicators(sym)

            if indicators:
                price_info["indicators"] = indicators
                price_info["analysis"] = self._format_indicator_analysis(
                    sym, data.price, indicators
                )

            enriched_prices[sym] = price_info

        return {
            "prices": enriched_prices,
            "count": len(price_data),
        }

    def _fetch_indicators(self, symbol: str) -> dict[str, object] | None:
        """Fetch latest technical indicators for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary of indicator values, or None if no data available
        """
        try:
            result = self.storage.query(
                """
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
                """,
                [symbol.upper()],
            )

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
                "stochastic": {
                    "k": row["stoch_k"],
                    "d": row["stoch_d"],
                },
                "date": str(row["date"]),
            }
        except Exception as e:
            logger.warning(f"Failed to fetch indicators for {symbol}: {e}")
            return None

    def _format_indicator_analysis(
        self, symbol: str, current_price: float, indicators: dict[str, object]
    ) -> str:
        """Format technical indicators into human-readable analysis text.

        Args:
            symbol: Stock symbol
            current_price: Current stock price
            indicators: Dictionary of indicator values

        Returns:
            Formatted analysis string for agent consumption
        """
        analysis_parts = [f"{symbol} current price ${current_price:.2f}"]

        # RSI analysis
        rsi = indicators.get("rsi_14")
        if isinstance(rsi, (int, float)) and rsi is not None:
            if rsi < 30:
                analysis_parts.append(f"RSI={rsi:.1f} (oversold)")
            elif rsi > 70:
                analysis_parts.append(f"RSI={rsi:.1f} (overbought)")
            else:
                analysis_parts.append(f"RSI={rsi:.1f} (neutral)")

        # MACD analysis
        macd_data = indicators.get("macd")
        if isinstance(macd_data, dict):
            macd_val = macd_data.get("macd")
            signal_val = macd_data.get("signal")
            if isinstance(macd_val, (int, float)) and isinstance(signal_val, (int, float)):
                if macd_val > signal_val:
                    analysis_parts.append("MACD bullish cross")
                elif macd_val < signal_val:
                    analysis_parts.append("MACD bearish cross")

        # Bollinger Bands analysis
        bbands = indicators.get("bbands")
        if isinstance(bbands, dict):
            bb_upper = bbands.get("upper")
            bb_lower = bbands.get("lower")
            bb_middle = bbands.get("middle")
            if (
                isinstance(bb_upper, (int, float))
                and isinstance(bb_lower, (int, float))
                and isinstance(bb_middle, (int, float))
            ):
                if current_price < bb_lower:
                    analysis_parts.append("below lower Bollinger Band")
                elif current_price > bb_upper:
                    analysis_parts.append("above upper Bollinger Band")
                elif current_price < bb_middle:
                    analysis_parts.append("near lower Bollinger Band")
                elif current_price > bb_middle:
                    analysis_parts.append("near upper Bollinger Band")

        # SMA 200 trend analysis
        sma_200 = indicators.get("sma_200")
        if isinstance(sma_200, (int, float)):
            if current_price > sma_200:
                pct_above = ((current_price - sma_200) / sma_200) * 100
                analysis_parts.append(f"{pct_above:.1f}% above 200-day SMA (uptrend)")
            else:
                pct_below = ((sma_200 - current_price) / sma_200) * 100
                analysis_parts.append(f"{pct_below:.1f}% below 200-day SMA (downtrend)")

        # Stochastic analysis
        stoch = indicators.get("stochastic")
        if isinstance(stoch, dict):
            stoch_k = stoch.get("k")
            if isinstance(stoch_k, (int, float)):
                if stoch_k < 20:
                    analysis_parts.append(f"Stochastic={stoch_k:.1f} (oversold)")
                elif stoch_k > 80:
                    analysis_parts.append(f"Stochastic={stoch_k:.1f} (overbought)")

        # Add trading signal interpretation
        signals = []
        if isinstance(rsi, (int, float)) and rsi < 30:
            signals.append("potential buy signal")
        if isinstance(rsi, (int, float)) and rsi > 70:
            signals.append("potential sell signal")

        if isinstance(macd_data, dict):
            macd_val = macd_data.get("macd")
            signal_val = macd_data.get("signal")
            if (
                isinstance(macd_val, (int, float))
                and isinstance(signal_val, (int, float))
                and isinstance(rsi, (int, float))
            ):
                if macd_val > signal_val and rsi < 50:
                    signals.append("bullish momentum building")
                elif macd_val < signal_val and rsi > 50:
                    signals.append("bearish momentum building")

        if signals:
            analysis_parts.append(f"- {', '.join(signals)}")

        return ", ".join(analysis_parts)


__all__ = ["DataTools"]
