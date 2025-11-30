import pytest
from unittest.mock import MagicMock, patch
from datetime import date, timedelta
from decimal import Decimal
import pandas as pd
from app.backtest.replay import replay_backtest, BacktestState

@pytest.fixture
def mock_storage():
    return MagicMock()

@pytest.fixture
def mock_strategy():
    strategy = MagicMock()
    strategy.should_enter.return_value = False
    strategy.should_exit.return_value = (False, None)
    return strategy

@patch("app.backtest.replay._fetch_ohlcv_data")
@patch("app.backtest.replay.calculate_indicators_from_df")
def test_replay_backtest_bulk_fetch(mock_calc_indicators, mock_fetch_data, mock_storage, mock_strategy):
    # Setup mock data
    start_date = date(2023, 1, 1)
    end_date = date(2023, 1, 5)
    
    # Create a DataFrame covering the period
    dates = pd.date_range(start="2022-12-01", end="2023-01-05")
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
    mock_calc_indicators.return_value = {
        "indicators": {"sma_20": 100.0},
        "interpretations": {}
    }
    
    # Run backtest
    state = replay_backtest(
        storage=mock_storage,
        run_id="test_run",
        symbol="AAPL",
        start_date=start_date,
        end_date=end_date,
        initial_capital=Decimal("10000"),
        strategy=mock_strategy
    )
    
    # Verify fetch was called once with large lookback
    mock_fetch_data.assert_called_once()
    call_args = mock_fetch_data.call_args[0]  # Positional args
    call_kwargs = mock_fetch_data.call_args[1]  # Keyword args
    assert call_args[1] == "AAPL"  # symbol is second positional arg
    assert call_kwargs["lookback_days"] == 10000
    
    # Verify indicators were calculated for each trading day (5 days)
    # 2023-01-01 to 2023-01-05 is 5 days
    assert mock_calc_indicators.call_count == 5
    
    # Verify state
    assert isinstance(state, BacktestState)
    assert len(state.equity_curve) == 5
