"""Agent tools for portfolio-ai.

This module provides tool definitions and executors for agents.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

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
        "description": "Fetch current price and analytics for stock symbols",
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

    def __init__(self, storage, news_source, fred_source, price_fetcher, portfolio_mgr, analytics):
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
        """Execute get_price_data tool."""
        price_data = self.price_fetcher.fetch_price_data(symbols)

        return {
            "prices": {sym: data.model_dump(mode="json") for sym, data in price_data.items()},
            "count": len(price_data),
        }

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
