"""
Benchmark comparison module for backtests.

Provides functionality for comparing strategy performance against buy-and-hold benchmarks:
- SPY/VTI buy-and-hold returns for same period
- Alpha calculation: strategy_return - [rf + beta * (benchmark_return - rf)]
- Information ratio: (strategy_return - benchmark_return) / tracking_error
- Tracking error: std_dev(strategy_returns - benchmark_returns)
- Side-by-side equity curve comparison

Phase B: Strategy Comparison Mode (VISION.md B2)
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import sqrt

import numpy as np

from app.backtest.comparison import NormalizedEquityPoint, normalize_equity_curve
from app.backtest.models import BacktestEquity
from app.logging_config import get_logger
from app.storage import PortfolioStorage

logger = get_logger(__name__)


@dataclass
class BenchmarkMetrics:
    """Performance metrics for benchmark comparison."""

    # Basic metrics
    strategy_return_pct: Decimal
    benchmark_return_pct: Decimal
    outperformance_pct: Decimal  # strategy - benchmark

    # Risk-adjusted metrics
    alpha: Decimal | None  # Jensen's alpha
    information_ratio: Decimal | None  # IR = excess return / tracking error
    tracking_error: Decimal | None  # Annualized std dev of return differences

    # Additional stats
    beta: Decimal | None  # Strategy beta vs benchmark
    correlation: float | None  # Correlation between strategy and benchmark returns

    # Metadata
    benchmark_symbol: str
    start_date: date
    end_date: date
    num_periods: int  # Number of overlapping data points


@dataclass
class BenchmarkComparison:
    """Complete comparison result: strategy vs benchmark."""

    # Normalized equity curves for visual comparison
    strategy_equity: list[NormalizedEquityPoint]
    benchmark_equity: list[NormalizedEquityPoint]

    # Performance metrics
    metrics: BenchmarkMetrics


class BenchmarkComparisonEngine:
    """Engine for comparing strategy performance against market benchmarks.

    Uses existing patterns from:
    - comparison.py: normalize_equity_curve for fair comparisons
    - price_fetcher.py: beta calculation using daily returns
    - metrics.py: Sharpe ratio patterns for risk-adjusted metrics
    """

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize benchmark comparison engine.

        Args:
            storage: PortfolioStorage instance for querying historical data
        """
        self.storage = storage

    def compare_to_benchmark(
        self,
        strategy_equity_curve: list[BacktestEquity],
        benchmark_symbol: str,
        start_date: date,
        end_date: date,
        risk_free_rate: Decimal = Decimal("0.045"),
    ) -> BenchmarkComparison:
        """Compare strategy performance to buy-and-hold benchmark.

        Args:
            strategy_equity_curve: Strategy's daily equity snapshots
            benchmark_symbol: Benchmark ticker (e.g., "SPY", "VTI")
            start_date: Backtest start date
            end_date: Backtest end date
            risk_free_rate: Annual risk-free rate (default: 4.5%)

        Returns:
            BenchmarkComparison with equity curves and metrics

        Raises:
            ValueError: If insufficient benchmark data available
        """
        if not strategy_equity_curve:
            raise ValueError("Strategy equity curve is empty")

        # Normalize strategy equity curve
        strategy_normalized = normalize_equity_curve(strategy_equity_curve)

        # Get buy-and-hold returns for benchmark
        benchmark_equity = self.get_buy_and_hold_returns(
            symbol=benchmark_symbol,
            start_date=start_date,
            end_date=end_date,
        )

        if not benchmark_equity:
            raise ValueError(
                f"No benchmark data available for {benchmark_symbol} "
                f"from {start_date} to {end_date}"
            )

        # Calculate performance metrics
        metrics = self._calculate_metrics(
            strategy_normalized=strategy_normalized,
            benchmark_normalized=benchmark_equity,
            benchmark_symbol=benchmark_symbol,
            start_date=start_date,
            end_date=end_date,
            risk_free_rate=risk_free_rate,
        )

        return BenchmarkComparison(
            strategy_equity=strategy_normalized,
            benchmark_equity=benchmark_equity,
            metrics=metrics,
        )

    def get_buy_and_hold_returns(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[NormalizedEquityPoint]:
        """Calculate buy-and-hold returns for a symbol over a period.

        Queries day_bars table for historical OHLCV data and converts to
        normalized equity curve (starting at 0% return).

        Args:
            symbol: Stock ticker (e.g., "SPY", "VTI")
            start_date: Start date for calculation
            end_date: End date for calculation

        Returns:
            List of normalized equity points representing buy-and-hold performance
            Empty list if no data available
        """
        # Query day_bars for historical prices
        df = self.storage.query(
            """
            SELECT date, close
            FROM day_bars
            WHERE ticker = ?
              AND date >= ?
              AND date <= ?
            ORDER BY date ASC
            """,
            [symbol, start_date.isoformat(), end_date.isoformat()],
        )

        if df.is_empty():
            logger.warning(
                "no_benchmark_data",
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
            )
            return []

        # Convert to normalized equity curve
        initial_price = df[0, "close"]
        if initial_price <= 0:
            logger.error(
                "invalid_initial_price",
                symbol=symbol,
                initial_price=initial_price,
            )
            return []

        result = []
        for row in df.iter_rows(named=True):
            date_val = row["date"]
            close_price = row["close"]

            # Calculate cumulative return from initial price
            cumulative_return_pct = ((close_price - initial_price) / initial_price) * 100

            result.append(
                NormalizedEquityPoint(
                    date=date_val,
                    cumulative_return_pct=Decimal(str(round(cumulative_return_pct, 4))),
                )
            )

        logger.info(
            "benchmark_returns_calculated",
            symbol=symbol,
            num_points=len(result),
            start_date=start_date,
            end_date=end_date,
            initial_price=initial_price,
            final_return_pct=result[-1].cumulative_return_pct if result else 0,
        )

        return result

    def calculate_alpha(
        self,
        strategy_return: Decimal,
        benchmark_return: Decimal,
        beta: Decimal,
        risk_free_rate: Decimal = Decimal("0.045"),
    ) -> Decimal:
        """Calculate Jensen's alpha.

        Alpha measures strategy's excess return over expected return based on CAPM:
        Alpha = Strategy_Return - [Risk_Free_Rate + Beta * (Benchmark_Return - Risk_Free_Rate)]

        Positive alpha indicates outperformance after adjusting for market risk.

        Args:
            strategy_return: Total strategy return (e.g., 0.15 for 15%)
            benchmark_return: Total benchmark return (e.g., 0.10 for 10%)
            beta: Strategy beta vs benchmark
            risk_free_rate: Annual risk-free rate (default: 4.5%)

        Returns:
            Alpha as decimal (e.g., 0.03 for 3% alpha)
        """
        # CAPM expected return: rf + beta * (benchmark_return - rf)
        market_premium = benchmark_return - risk_free_rate
        expected_return = risk_free_rate + beta * market_premium

        # Alpha = actual return - expected return
        alpha = strategy_return - expected_return

        return alpha

    def calculate_information_ratio(
        self,
        strategy_returns: list[float],
        benchmark_returns: list[float],
    ) -> Decimal | None:
        """Calculate information ratio (IR).

        IR = (Strategy_Return - Benchmark_Return) / Tracking_Error
        Measures excess return per unit of tracking error (active risk).

        IR interpretation:
        - < 0.0: Underperforming benchmark with tracking error
        - 0.0-0.5: Low information ratio
        - 0.5-1.0: Good active management
        - > 1.0: Excellent active management

        Args:
            strategy_returns: List of daily strategy returns
            benchmark_returns: List of daily benchmark returns

        Returns:
            Information ratio, or None if insufficient data
        """
        if len(strategy_returns) != len(benchmark_returns):
            logger.warning(
                "return_length_mismatch",
                strategy_len=len(strategy_returns),
                benchmark_len=len(benchmark_returns),
            )
            return None

        if len(strategy_returns) < 2:
            return None

        # Calculate tracking error (annualized)
        tracking_error = self.calculate_tracking_error(strategy_returns, benchmark_returns)
        if tracking_error is None or tracking_error == 0:
            return None

        # Calculate excess returns
        excess_returns = [s - b for s, b in zip(strategy_returns, benchmark_returns, strict=True)]
        mean_excess_return = sum(excess_returns) / len(excess_returns)

        # Annualize mean excess return
        annualized_excess_return = mean_excess_return * 252

        # IR = annualized excess return / tracking error
        information_ratio = Decimal(str(annualized_excess_return)) / tracking_error

        return Decimal(str(round(float(information_ratio), 4)))

    def calculate_tracking_error(
        self,
        strategy_returns: list[float],
        benchmark_returns: list[float],
    ) -> Decimal | None:
        """Calculate tracking error (annualized).

        Tracking error = Annualized standard deviation of (strategy_returns - benchmark_returns)
        Measures volatility of excess returns (active risk).

        Args:
            strategy_returns: List of daily strategy returns
            benchmark_returns: List of daily benchmark returns

        Returns:
            Annualized tracking error as decimal (e.g., 0.05 for 5%), or None if insufficient data
        """
        if len(strategy_returns) != len(benchmark_returns):
            return None

        if len(strategy_returns) < 2:
            return None

        # Calculate excess returns (strategy - benchmark)
        excess_returns = [s - b for s, b in zip(strategy_returns, benchmark_returns, strict=True)]

        # Calculate standard deviation of excess returns
        mean_excess = sum(excess_returns) / len(excess_returns)
        variance = sum((r - mean_excess) ** 2 for r in excess_returns) / (len(excess_returns) - 1)
        std_dev = sqrt(variance)

        # Annualize: daily std dev * sqrt(252 trading days)
        annualized_tracking_error = std_dev * sqrt(252)

        return Decimal(str(round(annualized_tracking_error, 4)))

    def _calculate_metrics(
        self,
        strategy_normalized: list[NormalizedEquityPoint],
        benchmark_normalized: list[NormalizedEquityPoint],
        benchmark_symbol: str,
        start_date: date,
        end_date: date,
        risk_free_rate: Decimal,
    ) -> BenchmarkMetrics:
        """Calculate comprehensive benchmark comparison metrics.

        Args:
            strategy_normalized: Normalized strategy equity curve
            benchmark_normalized: Normalized benchmark equity curve
            benchmark_symbol: Benchmark ticker symbol
            start_date: Backtest start date
            end_date: Backtest end date
            risk_free_rate: Annual risk-free rate

        Returns:
            BenchmarkMetrics with all comparison statistics
        """
        # Align dates for comparison
        strategy_dict = {point.date: point for point in strategy_normalized}
        benchmark_dict = {point.date: point for point in benchmark_normalized}

        common_dates = sorted(set(strategy_dict.keys()) & set(benchmark_dict.keys()))

        if not common_dates:
            # No overlapping dates - return basic metrics only
            strategy_return = (
                strategy_normalized[-1].cumulative_return_pct if strategy_normalized else Decimal("0")
            )
            benchmark_return = (
                benchmark_normalized[-1].cumulative_return_pct if benchmark_normalized else Decimal("0")
            )

            return BenchmarkMetrics(
                strategy_return_pct=strategy_return,
                benchmark_return_pct=benchmark_return,
                outperformance_pct=strategy_return - benchmark_return,
                alpha=None,
                information_ratio=None,
                tracking_error=None,
                beta=None,
                correlation=None,
                benchmark_symbol=benchmark_symbol,
                start_date=start_date,
                end_date=end_date,
                num_periods=0,
            )

        # Calculate daily returns for aligned dates
        strategy_returns = []
        benchmark_returns = []

        prev_strategy_return = 0.0
        prev_benchmark_return = 0.0

        for d in common_dates:
            strategy_point = strategy_dict[d]
            benchmark_point = benchmark_dict[d]

            # Daily return = change in cumulative return
            strategy_daily = float(strategy_point.cumulative_return_pct) - prev_strategy_return
            benchmark_daily = float(benchmark_point.cumulative_return_pct) - prev_benchmark_return

            strategy_returns.append(strategy_daily / 100.0)  # Convert percentage to decimal
            benchmark_returns.append(benchmark_daily / 100.0)

            prev_strategy_return = float(strategy_point.cumulative_return_pct)
            prev_benchmark_return = float(benchmark_point.cumulative_return_pct)

        # Final cumulative returns
        strategy_return_pct = strategy_dict[common_dates[-1]].cumulative_return_pct
        benchmark_return_pct = benchmark_dict[common_dates[-1]].cumulative_return_pct
        outperformance_pct = strategy_return_pct - benchmark_return_pct

        # Calculate beta and correlation
        beta = None
        correlation = None

        if len(strategy_returns) >= 10:
            strategy_arr = np.array(strategy_returns)
            benchmark_arr = np.array(benchmark_returns)

            # Filter non-finite values
            mask = np.isfinite(strategy_arr) & np.isfinite(benchmark_arr)
            strategy_arr = strategy_arr[mask]
            benchmark_arr = benchmark_arr[mask]

            if len(strategy_arr) >= 10:
                # Calculate beta: Cov(strategy, benchmark) / Var(benchmark)
                benchmark_variance = float(np.var(benchmark_arr, ddof=1))
                if benchmark_variance > 0 and not np.isnan(benchmark_variance):
                    covariance = float(np.cov(strategy_arr, benchmark_arr, ddof=1)[0, 1])
                    beta = Decimal(str(round(covariance / benchmark_variance, 4)))

                # Calculate correlation
                std_strategy = np.std(strategy_arr, ddof=1)
                std_benchmark = np.std(benchmark_arr, ddof=1)
                if std_strategy > 0 and std_benchmark > 0:
                    corr = float(np.corrcoef(strategy_arr, benchmark_arr)[0, 1])
                    if not np.isnan(corr):
                        correlation = round(corr, 4)

        # Calculate alpha
        alpha = None
        if beta is not None:
            strategy_return_decimal = strategy_return_pct / Decimal("100")  # Convert % to decimal
            benchmark_return_decimal = benchmark_return_pct / Decimal("100")
            alpha = self.calculate_alpha(
                strategy_return=strategy_return_decimal,
                benchmark_return=benchmark_return_decimal,
                beta=beta,
                risk_free_rate=risk_free_rate,
            )

        # Calculate tracking error and information ratio
        tracking_error = self.calculate_tracking_error(strategy_returns, benchmark_returns)
        information_ratio = self.calculate_information_ratio(strategy_returns, benchmark_returns)

        logger.info(
            "benchmark_metrics_calculated",
            strategy_return_pct=float(strategy_return_pct),
            benchmark_return_pct=float(benchmark_return_pct),
            outperformance_pct=float(outperformance_pct),
            alpha=float(alpha) if alpha else None,
            beta=float(beta) if beta else None,
            information_ratio=float(information_ratio) if information_ratio else None,
            tracking_error=float(tracking_error) if tracking_error else None,
            correlation=correlation,
            num_periods=len(common_dates),
        )

        return BenchmarkMetrics(
            strategy_return_pct=strategy_return_pct,
            benchmark_return_pct=benchmark_return_pct,
            outperformance_pct=outperformance_pct,
            alpha=alpha,
            information_ratio=information_ratio,
            tracking_error=tracking_error,
            beta=beta,
            correlation=correlation,
            benchmark_symbol=benchmark_symbol,
            start_date=start_date,
            end_date=end_date,
            num_periods=len(common_dates),
        )
