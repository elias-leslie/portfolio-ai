"""Agent tools for portfolio-ai.

This module provides tool definitions and executors for agents.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.portfolio.analytics import PortfolioAnalytics
    from app.portfolio.manager import PortfolioManager
    from app.portfolio.price_fetcher import PriceDataFetcher
    from app.sources.fred import FREDSource
    from app.sources.news import GoogleNewsSource
    from app.storage.facade import DuckDBStorage

logger = logging.getLogger(__name__)


def get_news_tool_definition() -> dict[str, Any]:
    """Get News API tool definition."""
    return {
        "name": "get_news",
        "description": "Fetch recent news headlines about the market or specific topics",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "News search query (e.g., 'stock market', 'technology sector')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of headlines to return (default 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    }


def get_economic_data_tool_definition() -> dict[str, Any]:
    """Get FRED economic data tool definition."""
    return {
        "name": "get_economic_data",
        "description": "Fetch latest economic indicators from FRED (VIX, rates, unemployment, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "indicators": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of indicators (VIX, TNX, FEDFUNDS, CPI_YOY, UNEMPLOYMENT, DXY)",
                },
            },
            "required": ["indicators"],
        },
    }


def get_portfolio_data_tool_definition() -> dict[str, Any]:
    """Get portfolio data tool definition."""
    return {
        "name": "get_portfolio_data",
        "description": "Fetch user's current portfolio positions and analytics",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    }


def get_price_data_tool_definition() -> dict[str, Any]:
    """Get price data tool definition."""
    return {
        "name": "get_price_data",
        "description": "Fetch current price, analytics, and technical indicators for stock symbols. "
        "Returns enriched data including RSI, MACD, Bollinger Bands, moving averages, ATR, "
        "and Stochastic oscillators with human-readable interpretations to support trading decisions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of stock symbols (e.g., ['AAPL', 'GOOGL'])",
                },
            },
            "required": ["symbols"],
        },
    }


def get_store_idea_tool_definition() -> dict[str, Any]:
    """Get store idea tool definition."""
    return {
        "name": "store_idea",
        "description": "Store an investment idea in the database",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Brief title for the idea"},
                "thesis": {
                    "type": "string",
                    "description": "Detailed investment thesis explaining the opportunity",
                },
                "action": {
                    "type": "string",
                    "description": "Specific action to take (e.g., 'Buy AAPL calls', 'Short SPY')",
                },
                "idea_type": {
                    "type": "string",
                    "description": "Type of idea: 'long', 'short', 'option', 'macro'",
                },
                "confidence_score": {
                    "type": "number",
                    "description": "Confidence score 0-100",
                },
                "risk_level": {
                    "type": "string",
                    "description": "Risk level: 'low', 'medium', 'high'",
                },
                "reward_estimate": {
                    "type": "string",
                    "description": "Expected reward/return estimate",
                },
                "portfolio_impact": {
                    "type": "string",
                    "description": "How this would impact the portfolio",
                },
                "risks": {
                    "type": "string",
                    "description": "Key risks to consider",
                },
            },
            "required": [
                "title",
                "thesis",
                "action",
                "idea_type",
                "confidence_score",
                "risk_level",
            ],
        },
    }


class AgentTools:
    """Execute agent tools with access to data sources and storage."""

    def __init__(
        self,
        storage: DuckDBStorage,
        news_source: GoogleNewsSource,
        fred_source: FREDSource,
        price_fetcher: PriceDataFetcher,
        portfolio_mgr: PortfolioManager,
        analytics: PortfolioAnalytics,
    ) -> None:
        """Initialize agent tools.

        Args:
            storage: DuckDBStorage instance
            news_source: GoogleNewsSource instance
            fred_source: FREDSource instance
            price_fetcher: PriceDataFetcher instance
            portfolio_mgr: PortfolioManager instance
            analytics: PortfolioAnalytics instance
        """
        self.storage = storage
        self.news_source = news_source
        self.fred_source = fred_source
        self.price_fetcher = price_fetcher
        self.portfolio_mgr = portfolio_mgr
        self.analytics = analytics

    def execute_get_news(self, query: str, max_results: int = 10) -> dict[str, Any]:
        """Execute get_news tool."""
        headlines = self.news_source.fetch_headlines(query, max_results)
        return {"headlines": headlines, "count": len(headlines)}

    def execute_get_economic_data(self, indicators: list[str]) -> dict[str, Any]:
        """Execute get_economic_data tool."""
        data = self.fred_source.fetch_multiple(indicators)
        return {"indicators": data, "count": len(data)}

    def execute_get_portfolio_data(self) -> dict[str, Any]:
        """Execute get_portfolio_data tool."""
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

    def execute_get_price_data(self, symbols: list[str]) -> dict[str, Any]:
        """Execute get_price_data tool with technical indicators.

        Fetches current price data and enriches it with technical indicators
        from the technical_indicators table. Returns formatted interpretations
        to help agents make informed trading decisions.
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

    def _fetch_indicators(self, ticker: str) -> dict[str, Any] | None:
        """Fetch latest technical indicators for a ticker.

        Args:
            ticker: Stock ticker symbol

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
                WHERE ticker = ?
                ORDER BY date DESC
                LIMIT 1
                """,
                [ticker.upper()],
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
            logger.warning(f"Failed to fetch indicators for {ticker}: {e}")
            return None

    def _format_indicator_analysis(
        self, ticker: str, current_price: float, indicators: dict[str, Any]
    ) -> str:
        """Format technical indicators into human-readable analysis text.

        Args:
            ticker: Stock ticker symbol
            current_price: Current stock price
            indicators: Dictionary of indicator values

        Returns:
            Formatted analysis string for agent consumption
        """
        analysis_parts = [f"{ticker} current price ${current_price:.2f}"]

        # RSI analysis
        rsi = indicators.get("rsi_14")
        if rsi is not None:
            if rsi < 30:
                analysis_parts.append(f"RSI={rsi:.1f} (oversold)")
            elif rsi > 70:
                analysis_parts.append(f"RSI={rsi:.1f} (overbought)")
            else:
                analysis_parts.append(f"RSI={rsi:.1f} (neutral)")

        # MACD analysis
        macd_data = indicators.get("macd")
        if macd_data and macd_data.get("macd") is not None:
            macd = macd_data["macd"]
            signal = macd_data["signal"]
            if macd > signal:
                analysis_parts.append("MACD bullish cross")
            elif macd < signal:
                analysis_parts.append("MACD bearish cross")

        # Bollinger Bands analysis
        bbands = indicators.get("bbands")
        if bbands and bbands.get("upper") is not None:
            bb_upper = bbands["upper"]
            bb_lower = bbands["lower"]
            bb_middle = bbands["middle"]

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
        if sma_200 is not None:
            if current_price > sma_200:
                pct_above = ((current_price - sma_200) / sma_200) * 100
                analysis_parts.append(f"{pct_above:.1f}% above 200-day SMA (uptrend)")
            else:
                pct_below = ((sma_200 - current_price) / sma_200) * 100
                analysis_parts.append(f"{pct_below:.1f}% below 200-day SMA (downtrend)")

        # Stochastic analysis
        stoch = indicators.get("stochastic")
        if stoch and stoch.get("k") is not None:
            stoch_k = stoch["k"]
            if stoch_k < 20:
                analysis_parts.append(f"Stochastic={stoch_k:.1f} (oversold)")
            elif stoch_k > 80:
                analysis_parts.append(f"Stochastic={stoch_k:.1f} (overbought)")

        # Add trading signal interpretation
        signals = []
        if rsi is not None and rsi < 30:
            signals.append("potential buy signal")
        if rsi is not None and rsi > 70:
            signals.append("potential sell signal")

        if macd_data and macd_data.get("macd") is not None:
            if macd_data["macd"] > macd_data["signal"] and rsi is not None and rsi < 50:
                signals.append("bullish momentum building")
            elif macd_data["macd"] < macd_data["signal"] and rsi is not None and rsi > 50:
                signals.append("bearish momentum building")

        if signals:
            analysis_parts.append(f"- {', '.join(signals)}")

        return ", ".join(analysis_parts)

    def execute_store_idea(self, agent_run_id: str, **idea_data: Any) -> dict[str, Any]:
        """Execute store_idea tool."""
        idea_id = str(uuid.uuid4())

        self.storage.insert_dict(
            "agent_ideas",
            {
                "id": idea_id,
                "agent_run_id": agent_run_id,
                "idea_type": idea_data.get("idea_type"),
                "title": idea_data.get("title"),
                "thesis": idea_data.get("thesis"),
                "action": idea_data.get("action"),
                "confidence_score": idea_data.get("confidence_score"),
                "risk_level": idea_data.get("risk_level"),
                "reward_estimate": idea_data.get("reward_estimate"),
                "portfolio_impact": idea_data.get("portfolio_impact"),
                "data_needed": idea_data.get("data_needed"),
                "risks": idea_data.get("risks"),
                "status": "pending",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            },
        )

        logger.info(f"Stored idea {idea_id}: {idea_data.get('title')}")

        return {"idea_id": idea_id, "status": "stored"}
