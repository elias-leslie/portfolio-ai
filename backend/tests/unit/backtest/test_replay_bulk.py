from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.backtest.replay import BacktestState, replay_backtest


@pytest.fixture
def mock_storage():
    return MagicMock()


@pytest.fixture
def mock_strategy():
    strategy = MagicMock()
    strategy.should_enter.return_value = False
    strategy.should_exit.return_value = (False, None)
    return strategy


@patch("app.backtest.replay._get_data_range")
@patch("app.backtest.replay._fetch_ohlcv_data")
@patch("app.backtest.replay.calculate_indicators_from_df")
def test_replay_backtest_bulk_fetch(
    mock_calc_indicators, mock_fetch_data, mock_get_data_range, mock_storage, mock_strategy
):
    # Setup mock data - use 250 trading days to satisfy the 200-day minimum
    start_date = date(2023, 1, 1)
    end_date = date(2023, 12, 31)

    # Mock the data range check to indicate we have data available
    # Return a range that covers the backtest period with buffer for lookback
    mock_get_data_range.return_value = (date(2022, 1, 1), date(2023, 12, 31))

    # Create a DataFrame covering the period with extra data for lookback (365 days before start)
    dates = pd.date_range(start="2022-01-01", end="2023-12-31", freq="B")  # Business days only
    data = {
        "open": [100.0] * len(dates),
        "high": [105.0] * len(dates),
        "low": [95.0] * len(dates),
        "close": [102.0] * len(dates),
        "volume": [1000] * len(dates),
    }
    df = pd.DataFrame(data, index=dates)
    mock_fetch_data.return_value = df

    # Mock indicator calculation
    mock_calc_indicators.return_value = {"indicators": {"sma_20": 100.0}, "interpretations": {}}

    # Run backtest
    state = replay_backtest(
        storage=mock_storage,
        run_id="test_run",
        symbol="AAPL",
        start_date=start_date,
        end_date=end_date,
        initial_capital=Decimal("10000"),
        strategy=mock_strategy,
    )

    # Verify fetch was called once with large lookback
    mock_fetch_data.assert_called_once()
    call_args = mock_fetch_data.call_args[0]  # Positional args
    call_kwargs = mock_fetch_data.call_args[1]  # Keyword args
    assert call_args[1] == "AAPL"  # symbol is second positional arg
    assert call_kwargs["lookback_days"] == 10000

    # Verify indicators were calculated for each trading day in 2023
    # Business days in 2023 (approximately 252 trading days)
    trading_days_2023 = len([d for d in dates if d.year == 2023])
    assert mock_calc_indicators.call_count == trading_days_2023

    # Verify state
    assert isinstance(state, BacktestState)
    assert len(state.equity_curve) == trading_days_2023
