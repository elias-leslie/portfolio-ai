"""Multi-symbol portfolio backtesting module.

Extends single-symbol replay.py patterns to run portfolio-level backtests:
- Multiple symbols simultaneously
- Portfolio-level equity tracking (cash + all positions)
- Position sizing: equal weight or custom weights
- Rebalancing: daily, weekly, or monthly
- Portfolio-level metrics: Sharpe, max drawdown, total return
- Uses covariance matrix for portfolio volatility calculation

Phase B MVP: Equal weight portfolios with periodic rebalancing
Phase C: Custom weights, dynamic rebalancing, risk parity
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    import pandas as pd
else:
    import pandas as pd

from app.analytics.covariance import (
    calculate_portfolio_volatility_from_covariance,
    get_covariance_matrix,
    update_covariance_matrix,
)
from app.analytics.indicators import _fetch_ohlcv_data, calculate_indicators_from_df
from app.backtest.metrics import (
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_total_return,
    calculate_win_rate,
)
from app.backtest.replay import (
    BacktestState,
    Strategy,
    enter_trade,
    exit_trade,
)
from app.storage.facade import PortfolioStorage

logger = logging.getLogger(__name__)


@dataclass
class PortfolioMetrics:
    """Portfolio-level performance metrics."""

    total_return_pct: Decimal
    sharpe_ratio: Decimal
    max_drawdown_pct: Decimal
    portfolio_volatility: Decimal
    win_rate_pct: Decimal
    profit_factor: Decimal
    total_trades: int
    avg_holding_days: Decimal
    final_equity: Decimal
    initial_capital: Decimal


@dataclass
class PortfolioBacktestResult:
    """Results from portfolio backtest."""

    run_id: str
    symbols: list[str]
    start_date: date
    end_date: date
    initial_capital: Decimal
    final_equity: Decimal
    state: BacktestState
    metrics: PortfolioMetrics
    rebalance_count: int


RebalanceFrequency = Literal["daily", "weekly", "monthly", "never"]


class PortfolioBacktest:
    """Multi-symbol portfolio backtesting engine.

    Manages portfolio-level state, position sizing, rebalancing, and metrics.
    Uses existing BacktestState pattern from replay.py.
    """

    def __init__(
        self,
        storage: PortfolioStorage,
        initial_capital: Decimal,
        strategy: Strategy,
        sizing_method: Literal["equal_weight", "custom_weights"] = "equal_weight",
        custom_weights: dict[str, float] | None = None,
        rebalance_freq: RebalanceFrequency = "monthly",
        min_position_size: Decimal = Decimal("1000.00"),
    ):
        """Initialize portfolio backtest engine.

        Args:
            storage: Database connection manager
            initial_capital: Starting cash for portfolio
            strategy: Strategy implementation (e.g., EnhancedSignalStrategy)
            sizing_method: "equal_weight" or "custom_weights"
            custom_weights: Optional dict mapping symbol to weight (must sum to ~1.0)
            rebalance_freq: How often to rebalance ("daily", "weekly", "monthly", "never")
            min_position_size: Minimum dollar size per position
        """
        self.storage = storage
        self.initial_capital = initial_capital
        self.strategy = strategy
        self.sizing_method = sizing_method
        self.custom_weights = custom_weights or {}
        self.rebalance_freq = rebalance_freq
        self.min_position_size = min_position_size

        self.rebalance_count = 0

    def _get_target_weights(self, symbols: list[str]) -> dict[str, Decimal]:
        """Calculate target weights for portfolio.

        Args:
            symbols: List of symbols in portfolio

        Returns:
            Dict mapping symbol to target weight (sums to 1.0)
        """
        if self.sizing_method == "custom_weights" and self.custom_weights:
            # Use custom weights, converting to Decimal
            weights = {}
            for symbol in symbols:
                weight = self.custom_weights.get(symbol, 0.0)
                weights[symbol] = Decimal(str(weight))
            return weights

        # Equal weight
        equal_weight = Decimal("1.0") / Decimal(str(len(symbols)))
        return dict.fromkeys(symbols, equal_weight)

    def _should_rebalance(self, backtest_date: date, last_rebalance: date | None) -> bool:
        """Determine if portfolio should rebalance.

        Args:
            backtest_date: Current backtest date
            last_rebalance: Last rebalance date (None if never rebalanced)

        Returns:
            True if should rebalance on this date
        """
        if self.rebalance_freq == "never":
            return False

        if last_rebalance is None:
            return True  # First rebalance

        if self.rebalance_freq == "daily":
            return True

        days_since = (backtest_date - last_rebalance).days

        if self.rebalance_freq == "weekly":
            return days_since >= 7

        if self.rebalance_freq == "monthly":
            return days_since >= 30

        return False

    def _rebalance_positions(
        self,
        state: BacktestState,
        run_id: str,
        symbols: list[str],
        backtest_date: date,
        current_prices: dict[str, Decimal],
    ) -> None:
        """Rebalance portfolio to target weights.

        Closes all positions and reopens at target allocations.

        Args:
            state: Current backtest state
            run_id: Backtest run ID
            symbols: List of symbols in portfolio
            backtest_date: Current date
            current_prices: Dict mapping symbol to current price
        """
        # Close all positions
        for symbol in list(state.positions.keys()):
            if symbol in current_prices:
                exit_trade(state, run_id, symbol, backtest_date, current_prices[symbol], "signal")

        # Calculate target allocations
        total_equity = state.get_total_equity(current_prices)
        target_weights = self._get_target_weights(symbols)

        # Open new positions at target weights
        for symbol, weight in target_weights.items():
            if symbol not in current_prices:
                continue

            target_value = total_equity * weight
            if target_value < self.min_position_size:
                logger.debug(
                    f"REBALANCE SKIP: {symbol} | "
                    f"Target ${target_value:.2f} < min ${self.min_position_size:.2f}"
                )
                continue

            price = current_prices[symbol]
            shares = int(target_value / price)

            if shares > 0:
                # Calculate cost
                cost = Decimal(str(shares)) * price
                if cost <= state.cash:
                    enter_trade(state, symbol, backtest_date, price, shares)
                else:
                    logger.debug(
                        f"REBALANCE INSUFFICIENT CASH: {symbol} | "
                        f"Need ${cost:.2f}, have ${state.cash:.2f}"
                    )

        self.rebalance_count += 1
        logger.info(
            f"REBALANCE #{self.rebalance_count}: {backtest_date} | "
            f"Equity: ${total_equity:.2f} | Positions: {len(state.positions)}"
        )

    def _get_trading_days_for_portfolio(
        self, symbols: list[str], start_date: date, end_date: date
    ) -> list[date]:
        """Get union of trading days across all symbols.

        Args:
            symbols: List of symbols
            start_date: Backtest start
            end_date: Backtest end

        Returns:
            Sorted list of trading days where at least one symbol has data
        """
        all_days: set[date] = set()

        for symbol in symbols:
            query = """
                SELECT DISTINCT date
                FROM day_bars
                WHERE ticker = $1
                  AND date >= $2
                  AND date <= $3
            """
            result_df = self.storage.query(query, [symbol, str(start_date), str(end_date)])

            if not result_df.is_empty():
                symbol_days = [row["date"] for row in result_df.to_dicts()]
                all_days.update(symbol_days)

        if not all_days:
            raise ValueError(f"No trading data found for any symbol in {symbols}")

        return sorted(all_days)

    def _calculate_portfolio_metrics(
        self,
        state: BacktestState,
        initial_capital: Decimal,
        start_date: date,
        end_date: date,
    ) -> PortfolioMetrics:
        """Calculate portfolio-level performance metrics.

        Args:
            state: Final backtest state
            initial_capital: Starting capital
            start_date: Backtest start date
            end_date: Backtest end date

        Returns:
            PortfolioMetrics dataclass
        """
        if not state.equity_curve:
            return PortfolioMetrics(
                total_return_pct=Decimal("0.0"),
                sharpe_ratio=Decimal("0.0"),
                max_drawdown_pct=Decimal("0.0"),
                portfolio_volatility=Decimal("0.0"),
                win_rate_pct=Decimal("0.0"),
                profit_factor=Decimal("0.0"),
                total_trades=0,
                avg_holding_days=Decimal("0.0"),
                final_equity=initial_capital,
                initial_capital=initial_capital,
            )

        final_equity = state.equity_curve[-1].equity

        # Basic metrics
        total_return = calculate_total_return(initial_capital, final_equity)
        max_dd = calculate_max_drawdown(state.equity_curve)
        sharpe = calculate_sharpe_ratio(state.equity_curve)

        # Trade metrics
        win_rate = calculate_win_rate(state.trades)
        profit_factor = calculate_profit_factor(state.trades)

        # Average holding period
        if state.trades:
            total_holding_days = sum(
                (trade.exit_date - trade.entry_date).days for trade in state.trades
            )
            avg_holding = Decimal(str(total_holding_days)) / Decimal(str(len(state.trades)))
        else:
            avg_holding = Decimal("0.0")

        # Portfolio volatility (uses covariance if available)
        portfolio_vol = Decimal("0.0")
        if len(state.trades) > 0:
            # Get unique symbols from trades
            symbols = list({trade.symbol for trade in state.trades})
            if len(symbols) > 1:
                # Calculate weights from final positions
                for _snapshot in state.equity_curve[-5:]:  # Look at last 5 days
                    # Need to extract prices from equity curve
                    # For now, use equal weight assumption
                    pass

                # Simplified: Use equal weights for volatility calculation
                weights = {symbol: 1.0 / len(symbols) for symbol in symbols}
                try:
                    # Update covariance matrix if needed
                    cov_matrix = get_covariance_matrix(self.storage, symbols, max_age_hours=24)
                    if cov_matrix is None:
                        update_covariance_matrix(self.storage, symbols)
                        cov_matrix = get_covariance_matrix(self.storage, symbols, max_age_hours=1)

                    if cov_matrix:
                        portfolio_vol_float = calculate_portfolio_volatility_from_covariance(
                            weights, cov_matrix
                        )
                        portfolio_vol = Decimal(str(portfolio_vol_float))
                except Exception as e:
                    logger.warning(f"Failed to calculate portfolio volatility: {e}")

        return PortfolioMetrics(
            total_return_pct=total_return,
            sharpe_ratio=sharpe,
            max_drawdown_pct=max_dd,
            portfolio_volatility=portfolio_vol,
            win_rate_pct=win_rate,
            profit_factor=profit_factor,
            total_trades=len(state.trades),
            avg_holding_days=avg_holding,
            final_equity=final_equity,
            initial_capital=initial_capital,
        )

    def run_portfolio_backtest(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date,
        run_id: str,
    ) -> PortfolioBacktestResult:
        """Execute portfolio backtest across multiple symbols.

        Args:
            symbols: List of symbols to include in portfolio
            start_date: Backtest start date
            end_date: Backtest end date
            run_id: Unique identifier for this backtest run

        Returns:
            PortfolioBacktestResult with final state and metrics

        Raises:
            ValueError: If no data found or invalid parameters
        """
        if not symbols:
            raise ValueError("Must provide at least one symbol")

        if len(symbols) == 1:
            logger.warning("Single symbol portfolio - consider using replay_backtest() instead")

        logger.info(
            f"Starting portfolio backtest: {len(symbols)} symbols | "
            f"{start_date} to {end_date} | Capital: ${self.initial_capital:.2f}"
        )

        # Initialize state
        state = BacktestState(cash=self.initial_capital, peak_equity=self.initial_capital)
        last_rebalance: date | None = None

        # Get trading days (union of all symbols)
        trading_days = self._get_trading_days_for_portfolio(symbols, start_date, end_date)
        logger.info(f"Running backtest over {len(trading_days)} trading days")

        # Pre-fetch OHLCV data for all symbols
        lookback_days = 365
        start_date - timedelta(days=lookback_days)

        symbol_data: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            try:
                df = _fetch_ohlcv_data(
                    self.storage,
                    symbol,
                    lookback_days=10000,
                    as_of_date=end_date,
                )
                if not df.empty:
                    symbol_data[symbol] = df
                    logger.debug(f"Loaded {len(df)} rows for {symbol}")
                else:
                    logger.warning(f"No data found for {symbol}")
            except Exception as e:
                logger.warning(f"Failed to load data for {symbol}: {e}")

        if not symbol_data:
            raise ValueError(f"No data available for any symbol in {symbols}")

        # Main backtest loop
        for backtest_date in trading_days:
            current_prices: dict[str, Decimal] = {}
            symbol_indicators: dict[str, dict] = {}  # type: ignore[type-arg]
            symbol_ohlcv: dict[str, dict] = {}  # type: ignore[type-arg]

            # Process each symbol
            for symbol in symbols:
                if symbol not in symbol_data:
                    continue

                df = symbol_data[symbol]

                # Get data slice up to current date
                current_data_slice = df.loc[: pd.Timestamp(backtest_date)]
                if len(current_data_slice) > 300:
                    current_data_slice = current_data_slice.iloc[-300:]

                if current_data_slice.empty:
                    continue

                # Get current bar
                current_bar = current_data_slice.iloc[-1]
                ohlcv = {
                    "open": float(current_bar["open"]),
                    "high": float(current_bar["high"]),
                    "low": float(current_bar["low"]),
                    "close": float(current_bar["close"]),
                    "volume": float(current_bar["volume"]),
                }
                symbol_ohlcv[symbol] = ohlcv
                current_prices[symbol] = Decimal(str(ohlcv["close"]))

                # Calculate indicators
                indicators_result = calculate_indicators_from_df(current_data_slice, symbol)
                symbol_indicators[symbol] = indicators_result["indicators"]

            if not current_prices:
                continue  # No data for any symbol on this day

            # Update excursions for open positions
            for symbol, position in state.positions.items():
                if symbol in current_prices:
                    position.update_excursions(current_prices[symbol])

            # Check for rebalancing
            if self._should_rebalance(backtest_date, last_rebalance):
                self._rebalance_positions(state, run_id, symbols, backtest_date, current_prices)
                last_rebalance = backtest_date
            else:
                # Normal trading logic (no rebalancing)

                # Check exits first
                for symbol in list(state.positions.keys()):
                    if symbol not in current_prices or symbol not in symbol_indicators:
                        continue

                    position = state.positions[symbol]
                    should_exit, exit_reason = self.strategy.should_exit(
                        position, backtest_date, symbol_indicators[symbol], symbol_ohlcv[symbol]
                    )
                    if should_exit:
                        exit_trade(
                            state, run_id, symbol, backtest_date, current_prices[symbol], exit_reason
                        )

                # Check entries (for symbols without positions)
                for symbol in symbols:
                    if (
                        symbol not in current_prices
                        or symbol not in symbol_indicators
                        or state.has_position(symbol)
                    ):
                        continue

                    if self.strategy.should_enter(
                        symbol, backtest_date, symbol_indicators[symbol], symbol_ohlcv[symbol]
                    ):
                        # Calculate position size based on target weight
                        target_weights = self._get_target_weights(symbols)
                        target_weight = target_weights.get(symbol, Decimal("0.0"))

                        if target_weight > 0:
                            # Estimate portfolio equity
                            portfolio_equity = state.get_total_equity(current_prices)
                            target_value = portfolio_equity * target_weight

                            if target_value >= self.min_position_size:
                                price = current_prices[symbol]
                                shares = int(target_value / price)
                                cost = Decimal(str(shares)) * price

                                if shares > 0 and cost <= state.cash:
                                    enter_trade(state, symbol, backtest_date, price, shares)

            # Record daily equity snapshot
            state.record_equity_snapshot(run_id, backtest_date, current_prices)

        # Close all open positions at end of backtest
        if trading_days:
            final_date = trading_days[-1]
            for symbol in list(state.positions.keys()):
                if symbol in current_prices:
                    exit_trade(state, run_id, symbol, final_date, current_prices[symbol], "eod")

        # Calculate portfolio metrics
        metrics = self._calculate_portfolio_metrics(state, self.initial_capital, start_date, end_date)

        logger.info(
            f"Portfolio backtest complete: {len(state.trades)} trades | "
            f"Final equity: ${metrics.final_equity:.2f} | "
            f"Return: {metrics.total_return_pct:.2f}% | "
            f"Sharpe: {metrics.sharpe_ratio:.2f} | "
            f"Max DD: {metrics.max_drawdown_pct:.2f}%"
        )

        return PortfolioBacktestResult(
            run_id=run_id,
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_equity=metrics.final_equity,
            state=state,
            metrics=metrics,
            rebalance_count=self.rebalance_count,
        )
