"""Tests for Pattern Day Trader rules."""

from unittest.mock import MagicMock

import polars as pl
import pytest

from app.analytics.pdt_rules import (
    PDT_DAY_TRADE_LIMIT,
    PDT_EQUITY_THRESHOLD,
    check_pdt_status,
    count_day_trades,
    get_account_equity,
    should_block_day_trade,
)


class TestCountDayTrades:
    """Tests for day trade counting."""

    def test_counts_day_trades(self) -> None:
        """Counts same-day open/close trades."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame({"day_trade_count": [3]})

        count = count_day_trades(storage, "default")

        assert count == 3

    def test_zero_day_trades(self) -> None:
        """Returns 0 when no day trades."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame({"day_trade_count": [0]})

        count = count_day_trades(storage, "default")

        assert count == 0

    def test_empty_result(self) -> None:
        """Returns 0 for empty result."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame()

        count = count_day_trades(storage, "default")

        assert count == 0


class TestGetAccountEquity:
    """Tests for account equity retrieval."""

    def test_returns_equity(self) -> None:
        """Returns account equity."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame({"equity": [50_000.0]})

        equity = get_account_equity(storage, "default")

        assert equity == 50_000.0

    def test_no_account_returns_zero(self) -> None:
        """Returns 0 when account not found."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame()

        equity = get_account_equity(storage, "unknown")

        assert equity == 0.0


class TestCheckPdtStatus:
    """Tests for PDT status checking."""

    def test_under_limit_no_restriction(self) -> None:
        """Under day trade limit with any equity - no restriction."""
        storage = MagicMock()
        storage.query.side_effect = [
            pl.DataFrame({"day_trade_count": [2]}),  # 2 day trades
            pl.DataFrame({"equity": [10_000.0]}),  # Under $25k
        ]

        can_trade, message, details = check_pdt_status(storage, "default")

        assert can_trade is True
        assert details["day_trades_used"] == 2
        assert details["trades_remaining"] == 1  # 3 - 2 = 1

    def test_at_limit_high_equity_allowed(self) -> None:
        """At limit (3 trades) with high equity - allowed but warned."""
        storage = MagicMock()
        storage.query.side_effect = [
            pl.DataFrame({"day_trade_count": [3]}),  # 3 day trades (at limit)
            pl.DataFrame({"equity": [50_000.0]}),  # Over $25k
        ]

        can_trade, message, details = check_pdt_status(storage, "default")

        assert can_trade is True
        assert "WARNING" in message
        assert details["trades_remaining"] == 0

    def test_at_limit_low_equity_blocked(self) -> None:
        """At limit with low equity - blocked."""
        storage = MagicMock()
        storage.query.side_effect = [
            pl.DataFrame({"day_trade_count": [3]}),  # 3 day trades (at limit)
            pl.DataFrame({"equity": [10_000.0]}),  # Under $25k
        ]

        can_trade, message, details = check_pdt_status(storage, "default")

        assert can_trade is False
        assert "BLOCKED" in message
        assert details["trades_remaining"] == 0

    def test_pdt_account_high_equity_unlimited(self) -> None:
        """PDT account (4+ trades) with high equity - unlimited."""
        storage = MagicMock()
        storage.query.side_effect = [
            pl.DataFrame({"day_trade_count": [5]}),  # 5 day trades (PDT)
            pl.DataFrame({"equity": [50_000.0]}),  # Over $25k
        ]

        can_trade, message, details = check_pdt_status(storage, "default")

        assert can_trade is True
        assert details["is_pdt_account"] is True
        assert details["trades_remaining"] == 999  # Unlimited

    def test_pdt_account_low_equity_restricted(self) -> None:
        """PDT account with low equity - restricted."""
        storage = MagicMock()
        storage.query.side_effect = [
            pl.DataFrame({"day_trade_count": [5]}),  # 5 day trades (PDT)
            pl.DataFrame({"equity": [10_000.0]}),  # Under $25k
        ]

        can_trade, message, details = check_pdt_status(storage, "default")

        assert can_trade is False
        assert "RESTRICTED" in message
        assert details["is_pdt_account"] is True
        assert details["trades_remaining"] == 0


class TestShouldBlockDayTrade:
    """Tests for quick block check."""

    def test_returns_false_when_allowed(self) -> None:
        """Returns False (don't block) when trading allowed."""
        storage = MagicMock()
        storage.query.side_effect = [
            pl.DataFrame({"day_trade_count": [1]}),
            pl.DataFrame({"equity": [10_000.0]}),
        ]

        should_block = should_block_day_trade(storage, "default")

        assert should_block is False

    def test_returns_true_when_blocked(self) -> None:
        """Returns True (block) when trading restricted."""
        storage = MagicMock()
        storage.query.side_effect = [
            pl.DataFrame({"day_trade_count": [5]}),  # PDT
            pl.DataFrame({"equity": [10_000.0]}),  # Under $25k
        ]

        should_block = should_block_day_trade(storage, "default")

        assert should_block is True
