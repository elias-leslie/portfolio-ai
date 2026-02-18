"""Tests for slippage tracking in paper trading (FEAT-210).

Tests cover:
1. Slippage calculation with FIXED_PCT and DYNAMIC models
2. Transaction logger stores slippage data
3. Order executor applies slippage to fills
4. Slippage metrics in order results
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.backtest.costs import SlippageModel, calculate_slippage


class TestSlippageCalculation:
    """Test slippage calculation from costs.py."""

    def test_no_slippage_model(self) -> None:
        """NONE model returns zero slippage."""
        slippage = calculate_slippage(
            price=Decimal("100.00"),
            shares=100,
            model=SlippageModel.NONE,
        )
        assert slippage == Decimal("0.00")

    def test_fixed_pct_slippage_default(self) -> None:
        """FIXED_PCT with default 5 bps."""
        slippage = calculate_slippage(
            price=Decimal("100.00"),
            shares=100,
            model=SlippageModel.FIXED_PCT,
            slippage_bps=Decimal("5.0"),
        )
        # 5 bps = 0.05% = 0.0005
        # $100 * 0.0005 = $0.05 per share
        assert slippage == Decimal("0.05")

    def test_fixed_pct_slippage_10bps(self) -> None:
        """FIXED_PCT with 10 bps."""
        slippage = calculate_slippage(
            price=Decimal("50.00"),
            shares=200,
            model=SlippageModel.FIXED_PCT,
            slippage_bps=Decimal("10.0"),
        )
        # 10 bps = 0.10% = 0.001
        # $50 * 0.001 = $0.05 per share
        assert slippage == Decimal("0.05")

    def test_dynamic_slippage_small_position(self) -> None:
        """DYNAMIC model with small position relative to ADV."""
        slippage = calculate_slippage(
            price=Decimal("100.00"),
            shares=1000,
            model=SlippageModel.DYNAMIC,
            average_daily_volume=1_000_000,  # 0.1% of ADV
            dynamic_factor=Decimal("0.1"),
        )
        # Position = 1000 / 1_000_000 = 0.001 (0.1% of ADV)
        # Slippage rate = 0.001 * 0.1 = 0.0001 (0.01%)
        # Slippage per share = $100 * 0.0001 = $0.01
        expected = Decimal("100.00") * (Decimal("1000") / Decimal("1000000")) * Decimal("0.1")
        assert slippage == expected

    def test_dynamic_slippage_large_position(self) -> None:
        """DYNAMIC model with large position relative to ADV."""
        slippage = calculate_slippage(
            price=Decimal("100.00"),
            shares=100_000,
            model=SlippageModel.DYNAMIC,
            average_daily_volume=1_000_000,  # 10% of ADV
            dynamic_factor=Decimal("0.1"),
        )
        # Position = 100_000 / 1_000_000 = 0.1 (10% of ADV)
        # Slippage rate = 0.1 * 0.1 = 0.01 (1%)
        # Slippage per share = $100 * 0.01 = $1.00
        expected = Decimal("100.00") * (Decimal("100000") / Decimal("1000000")) * Decimal("0.1")
        assert slippage == expected

    def test_dynamic_slippage_requires_adv(self) -> None:
        """DYNAMIC model raises error without ADV."""
        with pytest.raises(ValueError, match="requires positive average_daily_volume"):
            calculate_slippage(
                price=Decimal("100.00"),
                shares=100,
                model=SlippageModel.DYNAMIC,
            )


class TestTransactionLoggerSlippage:
    """Test transaction logger stores slippage data."""

    def test_log_entry_with_slippage(self) -> None:
        """Entry transactions store slippage fields."""
        from app.analytics.transaction_logger import TransactionLogger

        # Create mock storage
        mock_storage = MagicMock()
        mock_conn = MagicMock()
        mock_storage.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_storage.connection.return_value.__exit__ = MagicMock(return_value=False)

        logger = TransactionLogger(mock_storage)

        result = logger.log_entry(
            trade_id="test-trade-1",
            symbol="AAPL",
            shares=100,
            price=150.05,  # Fill price after slippage
            cash_before=10000.0,
            cash_after=10000.0 - 15005.0,
            expected_price=150.00,
            slippage_amount=5.0,
            slippage_bps=3.33,
            adv=5000000.0,
            slippage_model="DYNAMIC",
        )

        assert result is True
        # Verify execute was called with slippage params
        # Called twice: symbol upsert + transaction insert
        assert mock_conn.execute.call_count == 2
        # Get the transaction insert call (second call)
        call_args = mock_conn.execute.call_args_list[1][0]
        params = call_args[1]
        # Check slippage fields are in params (indices 9-13)
        assert params[9] == 150.00  # expected_price
        assert params[10] == 5.0  # slippage_amount
        assert params[11] == 3.33  # slippage_bps
        assert params[12] == 5000000.0  # adv
        assert params[13] == "DYNAMIC"  # slippage_model

    def test_log_exit_with_slippage(self) -> None:
        """Exit transactions store slippage fields."""
        from app.analytics.transaction_logger import TransactionLogger

        mock_storage = MagicMock()
        mock_conn = MagicMock()
        mock_storage.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_storage.connection.return_value.__exit__ = MagicMock(return_value=False)

        logger = TransactionLogger(mock_storage)

        result = logger.log_exit(
            trade_id="test-trade-1",
            symbol="AAPL",
            shares=100,
            price=159.95,  # Fill price after slippage (sell gets less)
            cash_before=0.0,
            cash_after=15995.0,
            pnl=990.0,
            expected_price=160.00,
            slippage_amount=5.0,
            slippage_bps=3.13,
            adv=5000000.0,
            slippage_model="DYNAMIC",
        )

        assert result is True
        # Called twice: symbol upsert + transaction insert
        assert mock_conn.execute.call_count == 2
        # Get the transaction insert call (second call)
        call_args = mock_conn.execute.call_args_list[1][0]
        params = call_args[1]
        # Check slippage fields
        assert params[9] == 160.00  # expected_price
        assert params[10] == 5.0  # slippage_amount
        assert params[11] == 3.13  # slippage_bps


class TestOrderExecutorSlippage:
    """Test order executor applies and tracks slippage."""

    @patch("app.analytics.slippage_calculator.calculate_adv")
    @patch("app.analytics.order_executor.execute_buy_order", return_value=(True, None))
    def test_buy_order_applies_slippage(
        self, mock_buy: MagicMock, mock_adv: MagicMock
    ) -> None:
        """Buy orders apply slippage (pay more than expected price)."""
        from app.analytics.order_executor import OrderExecutor

        # Setup mocks
        mock_adv.return_value = 1_000_000  # ADV for DYNAMIC model

        mock_storage = MagicMock()

        # Mock price fetcher
        mock_price_data = MagicMock()
        mock_price_data.price = 100.0

        executor = OrderExecutor(mock_storage)
        executor.cash_manager = MagicMock()
        executor.cash_manager.get_cash_balance.return_value = 100000.0

        executor.price_fetcher = MagicMock()
        executor.price_fetcher.fetch_price_data.return_value = {"AAPL": mock_price_data}

        executor.transaction_logger = MagicMock()

        result = executor.execute_market_order(
            symbol="AAPL",
            action="buy",
            shares=1000,
            account_id="test-account",
            apply_slippage=True,
        )

        assert result["filled"] is True
        assert result["expected_price"] == 100.0
        assert result["price"] > result["expected_price"]  # Slippage increases buy price
        assert result["slippage_amount"] > 0
        assert result["slippage_bps"] > 0
        assert result["slippage_model"] == "DYNAMIC"
        assert result["adv"] == 1_000_000

    @patch("app.analytics.slippage_calculator.calculate_adv")
    @patch("app.analytics.order_executor.execute_sell_order", return_value=(True, None))
    def test_sell_order_applies_slippage(self, mock_sell: MagicMock, mock_adv: MagicMock) -> None:
        """Sell orders apply slippage (receive less than expected price)."""
        from app.analytics.order_executor import OrderExecutor

        mock_adv.return_value = None  # No ADV, use FIXED_PCT

        mock_storage = MagicMock()

        executor = OrderExecutor(mock_storage)
        executor.cash_manager = MagicMock()
        executor.cash_manager.get_cash_balance.return_value = 0.0

        mock_price_data = MagicMock()
        mock_price_data.price = 100.0
        executor.price_fetcher = MagicMock()
        executor.price_fetcher.fetch_price_data.return_value = {"AAPL": mock_price_data}

        executor.transaction_logger = MagicMock()

        result = executor.execute_market_order(
            symbol="AAPL",
            action="sell",
            shares=100,
            account_id="test-account",
            apply_slippage=True,
        )

        assert result["filled"] is True
        assert result["expected_price"] == 100.0
        assert result["price"] < result["expected_price"]  # Slippage decreases sell price
        assert result["slippage_model"] == "FIXED_PCT"
        assert result["adv"] is None

    @patch("app.analytics.slippage_calculator.calculate_adv")
    @patch("app.analytics.order_executor.execute_buy_order", return_value=(True, None))
    def test_no_slippage_when_disabled(self, mock_buy: MagicMock, mock_adv: MagicMock) -> None:
        """When apply_slippage=False, no slippage is applied."""
        from app.analytics.order_executor import OrderExecutor

        mock_adv.return_value = 1_000_000

        mock_storage = MagicMock()

        executor = OrderExecutor(mock_storage)
        executor.cash_manager = MagicMock()
        executor.cash_manager.get_cash_balance.return_value = 100000.0

        mock_price_data = MagicMock()
        mock_price_data.price = 100.0
        executor.price_fetcher = MagicMock()
        executor.price_fetcher.fetch_price_data.return_value = {"AAPL": mock_price_data}

        executor.transaction_logger = MagicMock()

        result = executor.execute_market_order(
            symbol="AAPL",
            action="buy",
            shares=100,
            account_id="test-account",
            apply_slippage=False,  # Disable slippage
        )

        assert result["filled"] is True
        assert result["price"] == result["expected_price"]  # No slippage
        assert result["slippage_amount"] == 0.0
        assert result["slippage_bps"] == 0.0
        assert result["slippage_model"] == "NONE"


class TestSlippageIntegration:
    """Integration tests for end-to-end slippage flow."""

    def test_slippage_costs_accumulate(self) -> None:
        """Round-trip trade accumulates entry + exit slippage costs."""
        # Entry slippage: 5 bps on $100 = $0.05 per share
        # Exit slippage: 5 bps on $105 = $0.0525 per share
        # Total for 100 shares: $5.00 + $5.25 = $10.25 slippage cost

        entry_slippage = calculate_slippage(
            price=Decimal("100.00"),
            shares=100,
            model=SlippageModel.FIXED_PCT,
            slippage_bps=Decimal("5.0"),
        )

        exit_slippage = calculate_slippage(
            price=Decimal("105.00"),
            shares=100,
            model=SlippageModel.FIXED_PCT,
            slippage_bps=Decimal("5.0"),
        )

        total_slippage_cost = (entry_slippage + exit_slippage) * 100
        assert total_slippage_cost == Decimal("10.25")

    def test_dynamic_slippage_increases_with_position_size(self) -> None:
        """Larger positions have proportionally higher slippage."""
        adv = 1_000_000

        small_slippage = calculate_slippage(
            price=Decimal("100.00"),
            shares=1000,  # 0.1% of ADV
            model=SlippageModel.DYNAMIC,
            average_daily_volume=adv,
            dynamic_factor=Decimal("0.1"),
        )

        large_slippage = calculate_slippage(
            price=Decimal("100.00"),
            shares=10000,  # 1% of ADV
            model=SlippageModel.DYNAMIC,
            average_daily_volume=adv,
            dynamic_factor=Decimal("0.1"),
        )

        # Large position should have 10x the slippage per share
        assert large_slippage == small_slippage * 10
