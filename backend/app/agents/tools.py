"""Agent tools for portfolio-ai.

This module provides tool definitions and executors for agents.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from app.portfolio.analytics import PortfolioAnalytics
    from app.portfolio.manager import PortfolioManager
    from app.portfolio.price_fetcher import PriceDataFetcher
    from app.services import NewsService
    from app.sources.fred import FREDSource
    from app.storage.facade import PortfolioStorage

from app.analytics.order_executor import OrderExecutor
from app.analytics.paper_trading import create_paper_trade
from app.logging_config import get_logger

logger = get_logger(__name__)


def get_news_tool_definition() -> dict[str, object]:
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


def get_economic_data_tool_definition() -> dict[str, object]:
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


def get_portfolio_data_tool_definition() -> dict[str, object]:
    """Get portfolio data tool definition."""
    return {
        "name": "get_portfolio_data",
        "description": "Fetch user's current portfolio positions and analytics",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    }


def get_price_data_tool_definition() -> dict[str, object]:
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


def get_store_idea_tool_definition() -> dict[str, object]:
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


def get_add_ticker_tool_definition() -> dict[str, object]:
    """Get add_ticker tool definition for autonomous watchlist management."""
    return {
        "name": "add_ticker",
        "description": "Add a ticker to the watchlist for monitoring. Use when you discover an interesting "
        "opportunity. Ownership is tracked so you can remove tickers you added later.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., 'AAPL', 'TSLA')",
                },
                "reason": {
                    "type": "string",
                    "description": "Why you're adding this ticker (your thesis)",
                },
                "expected_return_pct": {
                    "type": "number",
                    "description": "Expected return percentage (e.g., 15.0 for 15%)",
                },
                "time_horizon_days": {
                    "type": "integer",
                    "description": "Time horizon in days (e.g., 30 for 1 month)",
                },
            },
            "required": ["ticker", "reason", "expected_return_pct", "time_horizon_days"],
        },
    }


def get_remove_ticker_tool_definition() -> dict[str, object]:
    """Get remove_ticker tool definition for autonomous watchlist management."""
    return {
        "name": "remove_ticker",
        "description": "Remove a ticker you previously added from the watchlist after your idea was "
        "invalidated. You can ONLY remove tickers YOU added (ownership validation enforced). "
        "Use when: (1) time threshold met (30+ days) AND (2) thesis invalidated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol to remove",
                },
                "reason": {
                    "type": "string",
                    "description": "Why you're removing this ticker (why thesis invalidated)",
                },
            },
            "required": ["ticker", "reason"],
        },
    }


def get_create_paper_trade_tool_definition() -> dict[str, object]:
    """Get create_paper_trade tool definition for autonomous paper trading."""
    return {
        "name": "create_paper_trade",
        "description": "Create a paper trade to test your investment thesis. Trade will be tracked with "
        "automatic exits based on target price, stop loss, or time limit. Cash management is automatic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol",
                },
                "action": {
                    "type": "string",
                    "description": "Trade action: 'buy' (go long) or 'sell' (go short)",
                },
                "thesis": {
                    "type": "string",
                    "description": "Your investment thesis for this trade",
                },
                "target_price": {
                    "type": "number",
                    "description": "Target exit price (optional, for profit taking)",
                },
                "stop_loss_pct": {
                    "type": "number",
                    "description": "Stop loss percentage (optional, default 2xATR)",
                },
            },
            "required": ["ticker", "action", "thesis"],
        },
    }


def get_send_message_tool_definition() -> dict[str, object]:
    """Get send_message_to_agent tool definition for inter-agent communication."""
    return {
        "name": "send_message_to_agent",
        "description": "Send a message to another agent for collaboration. Use this to ask questions, "
        "share data, or request validation from another agent type (gemini, claude, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "description": "Target agent type (e.g., 'gemini', 'claude', 'strategy_analyzer')",
                },
                "message_type": {
                    "type": "string",
                    "description": "Type of message: 'question', 'data', 'consensus'",
                },
                "message": {
                    "type": "string",
                    "description": "The message content",
                },
                "data": {
                    "type": "object",
                    "description": "Optional structured data to include with message",
                },
                "priority": {
                    "type": "integer",
                    "description": "Message priority 1-10 (1=urgent, 10=low, default=5)",
                },
            },
            "required": ["agent_type", "message_type", "message"],
        },
    }


def get_query_memory_tool_definition() -> dict[str, object]:
    """Get query_agent_memory tool definition for accessing shared workflow context."""
    return {
        "name": "query_agent_memory",
        "description": "Query shared workflow memory to access data from other agents in the same workflow",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "ID of the workflow to query",
                },
                "key": {
                    "type": "string",
                    "description": "Key to retrieve from shared context (e.g., 'analysis_result', 'risk_score')",
                },
            },
            "required": ["workflow_id", "key"],
        },
    }


def get_vote_decision_tool_definition() -> dict[str, object]:
    """Get vote_on_decision tool definition for multi-agent consensus."""
    return {
        "name": "vote_on_decision",
        "description": "Vote on a decision in a multi-agent workflow. Used for consensus mechanisms.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_id": {
                    "type": "string",
                    "description": "ID of the workflow",
                },
                "decision_id": {
                    "type": "string",
                    "description": "ID of the decision to vote on",
                },
                "vote": {
                    "type": "string",
                    "description": "Your vote: 'approve', 'reject', 'abstain'",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explanation for your vote",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence level 0-1 (used for weighted voting)",
                },
            },
            "required": ["workflow_id", "decision_id", "vote", "reasoning"],
        },
    }


def get_wait_response_tool_definition() -> dict[str, object]:
    """Get wait_for_agent_response tool definition for blocking on responses."""
    return {
        "name": "wait_for_agent_response",
        "description": "Wait for another agent to respond to a message. Blocks until response received or timeout.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "ID of the message to wait for response to",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Maximum time to wait in seconds (default 300)",
                },
            },
            "required": ["message_id"],
        },
    }


class AgentTools:
    """Execute agent tools with access to data sources and storage."""

    def __init__(
        self,
        storage: PortfolioStorage,
        news_service: NewsService,
        fred_source: FREDSource,
        price_fetcher: PriceDataFetcher,
        portfolio_mgr: PortfolioManager,
        analytics: PortfolioAnalytics,
    ) -> None:
        """Initialize agent tools.

        Args:
            storage: PortfolioStorage instance
            news_service: NewsService instance
            fred_source: FREDSource instance
            price_fetcher: PriceDataFetcher instance
            portfolio_mgr: PortfolioManager instance
            analytics: PortfolioAnalytics instance
        """
        self.storage = storage
        self.news_service = news_service
        self.fred_source = fred_source
        self.price_fetcher = price_fetcher
        self.portfolio_mgr = portfolio_mgr
        self.analytics = analytics
        self.order_executor = OrderExecutor(storage)

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
                "ticker": bundle.ticker,
                "summary": bundle.summary.model_dump(),
                "articles": [article.model_dump() for article in bundle.articles[:limit]],
                "count": len(bundle.articles),
            }
        except Exception as exc:
            logger.error("agent_get_news_failed", query=query, error=str(exc))
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

    def execute_store_idea(self, agent_run_id: str, **idea_data: Any) -> dict[str, object]:
        """Execute store_idea tool and automatically create a paper trade."""
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
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
        )

        logger.info(f"Stored idea {idea_id}: {idea_data.get('title')}")

        # Automatically create paper trade for this idea
        paper_trade = create_paper_trade(self.storage, idea_id)

        if paper_trade:
            logger.info(
                f"Created paper trade for idea {idea_id}: "
                f"{paper_trade['ticker']} @ ${paper_trade['entry_price']}"
            )
            return {
                "idea_id": idea_id,
                "status": "stored",
                "paper_trade_created": True,
                "ticker": paper_trade["ticker"],
            }
        logger.warning(f"Failed to create paper trade for idea {idea_id}")
        return {"idea_id": idea_id, "status": "stored", "paper_trade_created": False}

    def execute_add_ticker(
        self,
        agent_run_id: str,
        ticker: str,
        reason: str,
        expected_return_pct: float,
        time_horizon_days: int,
    ) -> dict[str, object]:
        """Execute add_ticker tool to autonomously add tickers to watchlist.

        Args:
            agent_run_id: ID of the agent run (for ownership tracking)
            ticker: Stock ticker symbol
            reason: Why adding this ticker
            expected_return_pct: Expected return percentage
            time_horizon_days: Time horizon in days

        Returns:
            Result dictionary with status and details
        """
        ticker = ticker.upper()

        # Check if ticker already exists
        existing = self.storage.query(
            "SELECT id, added_by FROM watchlist_items WHERE symbol = $1", [ticker]
        )

        if not existing.is_empty():
            added_by = existing.get_column("added_by")[0]
            return {
                "status": "exists",
                "ticker": ticker,
                "added_by": added_by,
                "message": f"{ticker} already in watchlist (added by {added_by})",
            }

        # Create watchlist item with ownership tracking
        item_id = str(uuid.uuid4())

        metadata = {
            "reason": reason,
            "expected_return_pct": expected_return_pct,
            "time_horizon_days": time_horizon_days,
            "added_by_agent": agent_run_id,
        }

        try:
            self.storage.insert_dict(
                "watchlist_items",
                {
                    "id": item_id,
                    "symbol": ticker,
                    "metadata": metadata,
                    "added_by": agent_run_id,
                    "added_at": datetime.now(UTC),
                    "created_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC),
                },
            )

            logger.info(f"Agent {agent_run_id} added {ticker} to watchlist: {reason}")

            return {
                "status": "added",
                "ticker": ticker,
                "item_id": item_id,
                "message": f"Added {ticker} to watchlist (expected {expected_return_pct}% in {time_horizon_days} days)",
            }

        except Exception as e:
            logger.error(f"Failed to add {ticker} to watchlist: {e}")
            return {
                "status": "error",
                "ticker": ticker,
                "error": str(e),
            }

    def execute_remove_ticker(
        self, agent_run_id: str, ticker: str, reason: str
    ) -> dict[str, object]:
        """Execute remove_ticker tool with ownership validation.

        Agents can ONLY remove tickers they added. This prevents agents from
        removing user-added tickers or tickers added by other agents.

        Args:
            agent_run_id: ID of the agent run
            ticker: Stock ticker symbol to remove
            reason: Why removing this ticker

        Returns:
            Result dictionary with status and details
        """
        ticker = ticker.upper()

        # Check if ticker exists and get ownership
        existing = self.storage.query(
            "SELECT id, added_by, added_at FROM watchlist_items WHERE symbol = $1", [ticker]
        )

        if existing.is_empty():
            return {
                "status": "not_found",
                "ticker": ticker,
                "message": f"{ticker} not in watchlist",
            }

        item_id = existing.get_column("id")[0]
        added_by = existing.get_column("added_by")[0]
        added_at = existing.get_column("added_at")[0]

        # Ownership validation
        if added_by != agent_run_id:
            if added_by == "user":
                return {
                    "status": "forbidden",
                    "ticker": ticker,
                    "added_by": added_by,
                    "message": f"Cannot remove {ticker} - user-added tickers can only be removed by users",
                }
            return {
                "status": "forbidden",
                "ticker": ticker,
                "added_by": added_by,
                "message": f"Cannot remove {ticker} - added by different agent ({added_by})",
            }

        # Time threshold check (30 days minimum)
        days_since_added = (datetime.now(UTC) - added_at).days
        if days_since_added < 30:
            return {
                "status": "too_soon",
                "ticker": ticker,
                "days_since_added": days_since_added,
                "message": f"Cannot remove {ticker} - only {days_since_added} days since added (need 30+)",
            }

        # Remove ticker
        try:
            with self.storage.connection() as conn:
                conn.execute("DELETE FROM watchlist_items WHERE id = $1", [item_id])

            logger.info(
                f"Agent {agent_run_id} removed {ticker} from watchlist after {days_since_added} days: {reason}"
            )

            return {
                "status": "removed",
                "ticker": ticker,
                "days_held": days_since_added,
                "message": f"Removed {ticker} from watchlist (held {days_since_added} days): {reason}",
            }

        except Exception as e:
            logger.error(f"Failed to remove {ticker}: {e}")
            return {
                "status": "error",
                "ticker": ticker,
                "error": str(e),
            }

    def execute_create_paper_trade(
        self,
        agent_run_id: str,
        ticker: str,
        action: str,
        thesis: str,
        target_price: float | None = None,
        stop_loss_pct: float | None = None,
    ) -> dict[str, object]:
        """Execute create_paper_trade tool for autonomous paper trading.

        Creates a paper trade with automatic cash management and position sizing.
        Uses 5% of account balance for position sizing (simple equal-weight).

        Args:
            agent_run_id: ID of the agent run
            ticker: Stock ticker symbol
            action: 'buy' or 'sell'
            thesis: Investment thesis
            target_price: Optional target exit price
            stop_loss_pct: Optional stop loss percentage

        Returns:
            Result dictionary with trade details or error
        """
        ticker = ticker.upper()
        action = action.lower()

        # Validate action
        if action not in ["buy", "sell"]:
            return {
                "status": "error",
                "error": f"Invalid action '{action}' (must be 'buy' or 'sell')",
            }

        # Calculate max affordable shares (5% of account)
        account_id = "paper_trading"
        max_shares = self.order_executor.calculate_max_shares(
            ticker, account_id, max_position_pct=0.05
        )

        if max_shares == 0:
            return {
                "status": "error",
                "ticker": ticker,
                "error": "Insufficient cash or failed to calculate position size",
            }

        # Create agent idea record
        idea_id = str(uuid.uuid4())

        self.storage.insert_dict(
            "agent_ideas",
            {
                "id": idea_id,
                "agent_run_id": agent_run_id,
                "idea_type": action,  # "buy" or "sell"
                "title": f"{action.capitalize()} {ticker}",
                "thesis": thesis,
                "action": f"{action.capitalize()} {max_shares} shares of {ticker}",
                "confidence_score": 70,  # Default confidence
                "risk_level": "medium",  # Default risk
                "status": "pending",
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
        )

        # Execute market order
        # Cast action to Literal type for type safety
        action_typed = cast(Literal["buy", "sell"], action)

        order_result = self.order_executor.execute_market_order(
            ticker=ticker,
            action=action_typed,
            shares=max_shares,
            account_id=account_id,
            trade_id=idea_id,
            notes=f"Agent paper trade: {thesis[:100]}",
        )

        if not order_result.get("filled"):
            error_msg = order_result.get("error", "Unknown error")
            logger.error(f"Failed to execute paper trade for {ticker}: {error_msg}")
            return {
                "status": "error",
                "ticker": ticker,
                "error": error_msg,
            }

        # Calculate stop loss price if not provided
        entry_price = order_result["price"]
        if stop_loss_pct is None:
            # Default: 2x ATR (will be calculated by paper trading update task)
            stop_loss_price = None
        elif action == "buy":
            stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
        else:  # sell (short)
            stop_loss_price = entry_price * (1 + stop_loss_pct / 100)

        # Create idea_outcomes record
        self.storage.insert_dict(
            "idea_outcomes",
            {
                "idea_id": idea_id,
                "agent_run_id": agent_run_id,
                "ticker": ticker,
                "idea_type": action,
                "entry_price": entry_price,
                "entry_date": datetime.now(UTC).date(),
                "target_price": target_price,
                "stop_loss_price": stop_loss_price,
                "current_price": entry_price,
                "current_return_pct": 0.0,
                "status": "open",
                "shares": max_shares,
                "entry_amount": order_result["amount"],
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
        )

        logger.info(
            f"Agent {agent_run_id} created paper trade: {action.upper()} {max_shares} {ticker} "
            f"@ ${entry_price:.2f} (${order_result['amount']:.2f})"
        )

        return {
            "status": "created",
            "trade_id": idea_id,
            "ticker": ticker,
            "action": action,
            "shares": max_shares,
            "entry_price": entry_price,
            "entry_amount": order_result["amount"],
            "target_price": target_price,
            "stop_loss_price": stop_loss_price,
            "cash_remaining": order_result["cash_after"],
            "message": f"Created paper trade: {action.upper()} {max_shares} {ticker} @ ${entry_price:.2f}",
        }

    def execute_send_message_to_agent(
        self,
        agent_run_id: str,
        agent_type: str,
        message_type: str,
        message: str,
        data: dict[str, Any] | None = None,
        priority: int = 5,
    ) -> dict[str, object]:
        """Execute send_message_to_agent tool for inter-agent communication.

        Args:
            agent_run_id: ID of the sending agent run
            agent_type: Target agent type (e.g., 'gemini', 'claude')
            message_type: Type of message ('question', 'data', 'consensus')
            message: Message content
            data: Optional structured data
            priority: Message priority 1-10 (default 5)

        Returns:
            Result dictionary with message_id and status
        """
        try:
            message_id = str(uuid.uuid4())

            # Build content JSONB
            content: dict[str, Any] = {
                "message": message,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            if data:
                content["data"] = data

            # Insert message
            self.storage.insert_dict(
                "agent_messages",
                {
                    "id": message_id,
                    "from_agent_run_id": agent_run_id,
                    "to_agent_type": agent_type,
                    "message_type": message_type,
                    "content": content,
                    "status": "pending",
                    "priority": priority,
                    "created_at": datetime.now(UTC),
                },
            )

            logger.info(
                f"Agent {agent_run_id} sent {message_type} message to {agent_type}: {message[:100]}"
            )

            return {
                "status": "sent",
                "message_id": message_id,
                "to_agent_type": agent_type,
                "message_type": message_type,
            }

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    def execute_query_agent_memory(self, workflow_id: str, key: str) -> dict[str, object]:
        """Execute query_agent_memory tool to access shared workflow context.

        Args:
            workflow_id: ID of the workflow
            key: Key to retrieve from shared context

        Returns:
            Result dictionary with value or error
        """
        try:
            # Query workflow shared context
            result = self.storage.query(
                "SELECT shared_context FROM agent_workflows WHERE id = $1",
                [workflow_id],
            )

            if result.is_empty():
                return {
                    "status": "not_found",
                    "workflow_id": workflow_id,
                    "error": f"Workflow {workflow_id} not found",
                }

            shared_context = result.get_column("shared_context")[0]

            # Extract key from context
            if key in shared_context:
                return {
                    "status": "found",
                    "workflow_id": workflow_id,
                    "key": key,
                    "value": shared_context[key],
                }
            return {
                "status": "key_not_found",
                "workflow_id": workflow_id,
                "key": key,
                "available_keys": list(shared_context.keys()),
            }

        except Exception as e:
            logger.error(f"Failed to query workflow memory: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    def execute_vote_on_decision(
        self,
        agent_run_id: str,
        workflow_id: str,
        decision_id: str,
        vote: str,
        reasoning: str,
        confidence: float | None = None,
    ) -> dict[str, object]:
        """Execute vote_on_decision tool for multi-agent consensus.

        Args:
            agent_run_id: ID of the voting agent run
            workflow_id: ID of the workflow
            decision_id: ID of the decision
            vote: Vote value ('approve', 'reject', 'abstain')
            reasoning: Explanation for vote
            confidence: Confidence level 0-1 (for weighted voting)

        Returns:
            Result dictionary with vote status
        """
        try:
            # Get current shared context
            result = self.storage.query(
                "SELECT shared_context FROM agent_workflows WHERE id = $1",
                [workflow_id],
            )

            if result.is_empty():
                return {
                    "status": "error",
                    "error": f"Workflow {workflow_id} not found",
                }

            shared_context = result.get_column("shared_context")[0]

            # Initialize votes structure if not exists
            if "votes" not in shared_context:
                shared_context["votes"] = {}

            if decision_id not in shared_context["votes"]:
                shared_context["votes"][decision_id] = []

            # Add vote
            vote_record = {
                "agent_run_id": agent_run_id,
                "vote": vote,
                "reasoning": reasoning,
                "confidence": confidence or 1.0,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            shared_context["votes"][decision_id].append(vote_record)

            # Update workflow context
            with self.storage.connection() as conn:
                conn.execute(
                    "UPDATE agent_workflows SET shared_context = $1, last_updated_at = $2 WHERE id = $3",
                    [shared_context, datetime.now(UTC), workflow_id],
                )

            logger.info(
                f"Agent {agent_run_id} voted {vote} on {decision_id} in workflow {workflow_id}"
            )

            return {
                "status": "voted",
                "workflow_id": workflow_id,
                "decision_id": decision_id,
                "vote": vote,
                "total_votes": len(shared_context["votes"][decision_id]),
            }

        except Exception as e:
            logger.error(f"Failed to record vote: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    def execute_wait_for_agent_response(
        self, message_id: str, timeout_seconds: int = 300
    ) -> dict[str, object]:
        """Execute wait_for_agent_response tool to wait for another agent's reply.

        NOTE: This is a simplified implementation that checks current status.
        A full implementation would use polling or async waiting with timeout.

        Args:
            message_id: ID of the message to wait for response to
            timeout_seconds: Maximum time to wait (default 300)

        Returns:
            Result dictionary with response status and content
        """
        try:
            # Query message status
            result = self.storage.query(
                "SELECT status, content, replied_at FROM agent_messages WHERE id = $1",
                [message_id],
            )

            if result.is_empty():
                return {
                    "status": "error",
                    "error": f"Message {message_id} not found",
                }

            status = result.get_column("status")[0]
            content = result.get_column("content")[0]
            replied_at = result.get_column("replied_at")[0]

            if status == "replied":
                return {
                    "status": "received",
                    "message_id": message_id,
                    "response": content,
                    "replied_at": replied_at.isoformat() if replied_at else None,
                }
            if status == "read":
                return {
                    "status": "waiting",
                    "message_id": message_id,
                    "message": "Message read but no reply yet",
                }
            # pending
            return {
                "status": "waiting",
                "message_id": message_id,
                "message": "Message not yet read",
            }

        except Exception as e:
            logger.error(f"Failed to check message response: {e}")
            return {
                "status": "error",
                "error": str(e),
            }
