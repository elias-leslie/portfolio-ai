"""Delegation methods for strategy storage backward compatibility.

This module provides pass-through methods to maintain backward compatibility
while delegating to specialized storage modules.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from .strategy_performance import get_performance_storage
from .strategy_queries import get_strategy_queries
from .strategy_seeds import get_seed_storage
from .strategy_signals import get_signal_storage
from .strategy_trades import get_trade_storage


class StrategyStorageDelegator:
    """Provides delegation methods for backward compatibility."""

    def __init__(self) -> None:
        """Initialize delegator with storage instances."""
        self._seed_storage = get_seed_storage()
        self._performance_storage = get_performance_storage()
        self._signal_storage = get_signal_storage()
        self._queries = get_strategy_queries()
        self._trade_storage = get_trade_storage()

    # Performance delegation
    def update_live_performance(
        self, strategy_id: str, trades_count: int, win_rate: float, sharpe_ratio: float
    ) -> None:
        """Update live performance metrics."""
        return self._performance_storage.update_live_performance(
            strategy_id, trades_count, win_rate, sharpe_ratio
        )

    def record_daily_performance(
        self,
        strategy_id: str,
        perf_date: date,
        trades_today: int,
        wins_today: int,
        losses_today: int,
        pnl_today: Decimal,
        trades_30d: int,
        win_rate_30d: float,
        sharpe_ratio_30d: float,
        max_drawdown_30d: float,
        status: Literal["active", "underperforming"] = "active",
        notes: str | None = None,
    ) -> None:
        """Record daily performance metrics."""
        return self._performance_storage.record_daily_performance(
            strategy_id,
            perf_date,
            trades_today,
            wins_today,
            losses_today,
            pnl_today,
            trades_30d,
            win_rate_30d,
            sharpe_ratio_30d,
            max_drawdown_30d,
            status,
            notes,
        )

    def get_performance_history(self, strategy_id: str, limit: int = 30) -> list[dict[str, Any]]:
        """Get performance history for a strategy."""
        return self._performance_storage.get_performance_history(strategy_id, limit)

    # Query delegation
    def get_symbols_needing_strategies(self, max_symbols: int) -> list[tuple[Any, ...]]:
        """Get symbols that need strategy generation."""
        return self._queries.get_symbols_needing_strategies(max_symbols)

    def get_underperforming_strategies(
        self, performance_threshold: float | None = None, limit: int = 5
    ) -> list[tuple[Any, ...]]:
        """Get active strategies with performance below threshold."""
        return self._queries.get_underperforming_strategies(performance_threshold, limit)

    # Trade delegation
    def get_strategy_trades(self, strategy_id: str, cutoff_date: date) -> list[tuple[Any, Any]]:
        """Get trades for a strategy since cutoff date."""
        return self._trade_storage.get_strategy_trades(strategy_id, cutoff_date)

    def get_backtest_runs(self, strategy_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Get backtest runs for a strategy."""
        return self._trade_storage.get_backtest_runs(strategy_id, limit)

    def get_symbol_trades(self, symbol: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent trades for a symbol."""
        return self._trade_storage.get_symbol_trades(symbol, limit)

    # Seed delegation
    def get_strategy_seed(self, seed_id: str) -> tuple[str, float] | None:
        """Get strategy seed details."""
        return self._seed_storage.get_strategy_seed(seed_id)

    def get_seed_by_strategy_id(self, strategy_id: str) -> dict[str, Any] | None:
        """Get seed info for a strategy."""
        return self._seed_storage.get_seed_by_strategy_id(strategy_id)

    def link_strategy_to_seed(
        self, strategy_id: str, seed_id: str, seed_thesis: str, seed_confidence: float
    ) -> None:
        """Link a generated strategy back to its seed."""
        return self._seed_storage.link_strategy_to_seed(
            strategy_id, seed_id, seed_thesis, seed_confidence
        )

    def reject_seed(self, seed_id: str) -> None:
        """Mark a seed as rejected."""
        return self._seed_storage.reject_seed(seed_id)

    def list_seeds(
        self, status: str | None = None, symbol: str | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[tuple[Any, ...]], int]:
        """List strategy seeds with optional filtering."""
        return self._seed_storage.list_seeds(status, symbol, limit, offset)

    def get_seed_by_id(self, seed_id: str) -> tuple[Any, ...] | None:
        """Get a specific strategy seed by ID."""
        return self._seed_storage.get_seed_by_id(seed_id)

    # Signal delegation
    def get_strategy_signals(self, strategy_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent signals for a strategy."""
        return self._signal_storage.get_strategy_signals(strategy_id, limit)

    def store_signal(self, signal_data: dict[str, Any]) -> str | None:
        """Store a generated signal in the database."""
        return self._signal_storage.store_signal(signal_data)
