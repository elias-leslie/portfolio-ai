"""Agent tool definitions for Claude API.

This module provides tool schema definitions for all agent tools.
Tool definitions describe the interface (name, description, parameters)
that agents use to interact with the system.

For tool execution logic, see tool_executors_*.py modules.
"""

from __future__ import annotations


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


def get_add_symbol_tool_definition() -> dict[str, object]:
    """Get add_symbol tool definition for autonomous watchlist management."""
    return {
        "name": "add_symbol",
        "description": "Add a symbol to the watchlist for monitoring. Use when you discover an interesting "
        "opportunity. Ownership is tracked so you can remove symbols you added later.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol (e.g., 'AAPL', 'TSLA')",
                },
                "reason": {
                    "type": "string",
                    "description": "Why you're adding this symbol (your thesis)",
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
            "required": ["symbol", "reason", "expected_return_pct", "time_horizon_days"],
        },
    }


def get_remove_symbol_tool_definition() -> dict[str, object]:
    """Get remove_symbol tool definition for autonomous watchlist management."""
    return {
        "name": "remove_symbol",
        "description": "Remove a symbol you previously added from the watchlist after your idea was "
        "invalidated. You can ONLY remove symbols YOU added (ownership validation enforced). "
        "Use when: (1) time threshold met (30+ days) AND (2) thesis invalidated.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol to remove",
                },
                "reason": {
                    "type": "string",
                    "description": "Why you're removing this symbol (why thesis invalidated)",
                },
            },
            "required": ["symbol", "reason"],
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
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol",
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
            "required": ["symbol", "action", "thesis"],
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


def get_run_backtest_tool_definition() -> dict[str, object]:
    """Get run_backtest tool definition for strategy validation."""
    return {
        "name": "run_backtest",
        "description": "Execute a backtest to validate a trading strategy using historical data. "
        "Returns performance metrics including Sharpe ratio, win rate, max drawdown, and total return.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Stock symbol (e.g., 'AAPL', 'NVDA')",
                },
                "start_date": {
                    "type": "string",
                    "description": "Backtest start date (ISO format: YYYY-MM-DD)",
                },
                "end_date": {
                    "type": "string",
                    "description": "Backtest end date (ISO format: YYYY-MM-DD)",
                },
                "strategy": {
                    "type": "string",
                    "description": "Strategy name (default: 'signal_classifier')",
                    "default": "signal_classifier",
                },
                "min_signal_strength": {
                    "type": "integer",
                    "description": "Minimum signal strength for entry (1-10, default: 7)",
                    "default": 7,
                },
                "max_holding_days": {
                    "type": "integer",
                    "description": "Maximum holding period in days (default: 60)",
                    "default": 60,
                },
                "position_sizing_method": {
                    "type": "string",
                    "description": "Position sizing method: 'fixed_dollars' or 'fixed_shares' (default: 'fixed_dollars')",
                    "default": "fixed_dollars",
                },
                "position_size_value": {
                    "type": "number",
                    "description": "Position size in dollars or shares (default: 10000.00)",
                    "default": 10000.00,
                },
            },
            "required": ["symbol", "start_date", "end_date"],
        },
    }


__all__ = [
    "get_add_symbol_tool_definition",
    "get_create_paper_trade_tool_definition",
    "get_economic_data_tool_definition",
    "get_news_tool_definition",
    "get_portfolio_data_tool_definition",
    "get_price_data_tool_definition",
    "get_query_memory_tool_definition",
    "get_remove_symbol_tool_definition",
    "get_run_backtest_tool_definition",
    "get_send_message_tool_definition",
    "get_store_idea_tool_definition",
    "get_vote_decision_tool_definition",
    "get_wait_response_tool_definition",
]
