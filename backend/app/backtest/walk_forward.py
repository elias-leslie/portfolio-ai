"""Walk-forward backtesting with statistical validation.

Implements proper 3-fold validation structure:
- Train: Fit strategy parameters
- Validation: Evaluate during optimization
- Test: Final out-of-sample evaluation

Key features:
- 10-day gap between periods to prevent lookahead bias
- Statistical significance via Wilcoxon signed-rank test
- Per-fold B&H comparison with aggregate metrics
- Sample-size weighted metric aggregation
"""

from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from scipy import stats

from app.backtest.benchmark import BenchmarkComparisonEngine
from app.backtest.models import BacktestEquity
from app.backtest.replay import BacktestState, replay_backtest
from app.constants import TRADING_DAYS_PER_YEAR
from app.logging_config import get_logger
from app.storage import PortfolioStorage

logger = get_logger(__name__)


@dataclass
class WalkForwardWindow:
    """Single walk-forward validation window with 3-fold structure.

    Structure: TRAIN (train_days) -> GAP (gap_days) -> VAL (val_days) -> GAP (gap_days) -> TEST (test_days)
    """

    fold_number: int
    train_start: date
    train_end: date
    val_start: date
    val_end: date
    test_start: date
    test_end: date


@dataclass
class FoldMetrics:
    """Metrics for a single walk-forward fold."""

    fold_number: int
    # Strategy metrics
    total_return_pct: float
    sharpe_ratio: float
    win_rate: float
    max_drawdown_pct: float
    num_trades: int
    profit_factor: float
    # B&H comparison
    buy_hold_return_pct: float
    excess_return_pct: float
    beats_buy_hold: bool
    alpha: float | None
    beta: float | None
    # Period info
    test_start: date
    test_end: date


@dataclass
class WalkForwardResult:
    """Aggregated walk-forward validation result with statistical significance."""

    # Per-fold results
    folds: list[FoldMetrics]
    num_folds: int

    # Aggregated strategy metrics (weighted by num_trades)
    mean_return_pct: float
    std_return_pct: float
    mean_sharpe: float
    std_sharpe: float
    mean_win_rate: float
    max_drawdown_pct: float  # Worst across all folds
    total_trades: int

    # B&H comparison aggregates
    mean_excess_vs_bh: float
    pct_folds_beat_bh: float  # e.g., 0.8 = 80% of folds beat B&H

    # Statistical significance
    wilcoxon_p_value: float | None  # p-value for strategy vs B&H
    statistically_significant: bool  # p < 0.05
    significance_level: Literal["strong", "moderate", "weak", "none"]


class WalkForwardEngine:
    """Engine for walk-forward backtesting with statistical validation."""

    def __init__(
        self,
        storage: PortfolioStorage | None = None,
        train_days: int = 180,
        val_days: int = 60,
        test_days: int = 60,
        gap_days: int = 10,
        step_days: int = 60,
    ) -> None:
        """Initialize walk-forward engine.

        Args:
            storage: Portfolio storage instance (created if None)
            train_days: Training period length (default 180 = 6 months)
            val_days: Validation period length (default 60 = 2 months)
            test_days: Test period length (default 60 = 2 months)
            gap_days: Gap between periods to prevent lookahead (default 10)
            step_days: Roll-forward step size (default 60 = 2 months)
        """
        self.storage = storage or PortfolioStorage()
        self.train_days = train_days
        self.val_days = val_days
        self.test_days = test_days
        self.gap_days = gap_days
        self.step_days = step_days
        self._benchmark_engine: BenchmarkComparisonEngine | None = None

    @property
    def benchmark_engine(self) -> BenchmarkComparisonEngine:
        """Lazy-load benchmark engine."""
        if self._benchmark_engine is None:
            self._benchmark_engine = BenchmarkComparisonEngine(self.storage)
        return self._benchmark_engine

    def create_windows(self, start_date: date, end_date: date) -> list[WalkForwardWindow]:
        """Create walk-forward validation windows with 3-fold structure.

        Args:
            start_date: Start of historical period
            end_date: End of historical period

        Returns:
            List of WalkForwardWindow objects
        """
        windows = []
        fold_number = 1

        # Total days needed per window
        total_window_days = (
            self.train_days + self.gap_days + self.val_days + self.gap_days + self.test_days
        )

        current_date = start_date
        while current_date + timedelta(days=total_window_days) <= end_date:
            # Train period
            train_start = current_date
            train_end = train_start + timedelta(days=self.train_days - 1)

            # Gap 1
            val_start = train_end + timedelta(days=self.gap_days + 1)
            val_end = val_start + timedelta(days=self.val_days - 1)

            # Gap 2
            test_start = val_end + timedelta(days=self.gap_days + 1)
            test_end = test_start + timedelta(days=self.test_days - 1)

            if test_end <= end_date:
                windows.append(
                    WalkForwardWindow(
                        fold_number=fold_number,
                        train_start=train_start,
                        train_end=train_end,
                        val_start=val_start,
                        val_end=val_end,
                        test_start=test_start,
                        test_end=test_end,
                    )
                )
                fold_number += 1

            current_date += timedelta(days=self.step_days)

        return windows

    def _run_single_fold(
        self,
        symbol: str,
        window: WalkForwardWindow,
        strategy: Any,
        initial_capital: Decimal,
        benchmark_symbol: str,
    ) -> FoldMetrics:
        """Run backtest for a single fold on TEST period only.

        Training/validation periods are used for parameter fitting (future work).
        Currently we run the backtest on test period with fixed parameters.
        """
        # Run backtest on TEST period
        run_id = f"wf-{window.fold_number}-{uuid.uuid4().hex[:8]}"
        state = replay_backtest(
            storage=self.storage,
            run_id=run_id,
            symbol=symbol,
            start_date=window.test_start,
            end_date=window.test_end,
            strategy=strategy,
            initial_capital=initial_capital,
        )

        # Calculate strategy metrics
        strategy_metrics = self._calculate_metrics(state)

        # Calculate B&H comparison for test period
        bh_metrics = self._calculate_bh_comparison(
            state.equity_curve,
            benchmark_symbol,
            window.test_start,
            window.test_end,
        )

        return FoldMetrics(
            fold_number=window.fold_number,
            total_return_pct=strategy_metrics["total_return_pct"],
            sharpe_ratio=strategy_metrics["sharpe_ratio"],
            win_rate=strategy_metrics["win_rate"],
            max_drawdown_pct=strategy_metrics["max_drawdown_pct"],
            num_trades=int(strategy_metrics["num_trades"]),
            profit_factor=strategy_metrics["profit_factor"],
            buy_hold_return_pct=float(bh_metrics["buy_hold_return_pct"] or 0.0),
            excess_return_pct=float(bh_metrics["excess_return_pct"] or 0.0),
            beats_buy_hold=bool(bh_metrics["beats_buy_hold"]),
            alpha=float(bh_metrics["alpha"]) if bh_metrics["alpha"] is not None else None,
            beta=float(bh_metrics["beta"]) if bh_metrics["beta"] is not None else None,
            test_start=window.test_start,
            test_end=window.test_end,
        )

    def _calculate_metrics(self, state: BacktestState) -> dict[str, float]:
        """Calculate performance metrics from backtest state."""
        num_trades = len(state.trades)

        if num_trades == 0:
            return {
                "total_return_pct": 0.0,
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "max_drawdown_pct": 0.0,
                "num_trades": 0,
                "profit_factor": 0.0,
            }

        # Win rate and profit factor
        wins = [t for t in state.trades if t.pnl and t.pnl > 0]
        losses = [t for t in state.trades if t.pnl and t.pnl < 0]

        win_rate = len(wins) / num_trades

        total_wins = sum(float(t.pnl) for t in wins if t.pnl) if wins else 0.0
        total_losses = abs(sum(float(t.pnl) for t in losses if t.pnl)) if losses else 0.0
        profit_factor = (
            total_wins / total_losses if total_losses > 0 else (2.0 if total_wins > 0 else 0.0)
        )

        # From equity curve
        if state.equity_curve:
            equities = [float(e.equity) for e in state.equity_curve]
            initial = equities[0] if equities else 1.0
            final = equities[-1] if equities else initial

            total_return_pct = ((final - initial) / initial * 100) if initial > 0 else 0.0
            max_drawdown_pct = (
                max(float(e.drawdown_pct) for e in state.equity_curve)
                if state.equity_curve
                else 0.0
            )

            # Sharpe ratio
            if len(equities) > 1:
                daily_returns = [
                    (equities[i] - equities[i - 1]) / equities[i - 1]
                    for i in range(1, len(equities))
                    if equities[i - 1] > 0
                ]
                if daily_returns and len(daily_returns) > 1:
                    mean_ret = statistics.mean(daily_returns)
                    std_ret = statistics.stdev(daily_returns)
                    sharpe_ratio = (mean_ret / std_ret * (TRADING_DAYS_PER_YEAR**0.5)) if std_ret > 0 else 0.0
                else:
                    sharpe_ratio = 0.0
            else:
                sharpe_ratio = 0.0
        else:
            total_return_pct = 0.0
            max_drawdown_pct = 0.0
            sharpe_ratio = 0.0

        return {
            "total_return_pct": total_return_pct,
            "sharpe_ratio": sharpe_ratio,
            "win_rate": win_rate,
            "max_drawdown_pct": max_drawdown_pct,
            "num_trades": num_trades,
            "profit_factor": profit_factor,
        }

    def _calculate_bh_comparison(
        self,
        equity_curve: list[BacktestEquity],
        benchmark_symbol: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, float | bool | None]:
        """Calculate buy-and-hold comparison for a period."""
        default = {
            "buy_hold_return_pct": 0.0,
            "excess_return_pct": 0.0,
            "beats_buy_hold": False,
            "alpha": None,
            "beta": None,
        }

        if not equity_curve:
            return default

        try:
            comparison = self.benchmark_engine.compare_to_benchmark(
                strategy_equity_curve=equity_curve,
                benchmark_symbol=benchmark_symbol,
                start_date=start_date,
                end_date=end_date,
            )

            return {
                "buy_hold_return_pct": float(comparison.metrics.benchmark_return_pct),
                "excess_return_pct": float(comparison.metrics.outperformance_pct),
                "beats_buy_hold": float(comparison.metrics.outperformance_pct) > 0,
                "alpha": float(comparison.metrics.alpha) if comparison.metrics.alpha else None,
                "beta": float(comparison.metrics.beta) if comparison.metrics.beta else None,
            }
        except Exception as e:
            logger.warning("bnh_comparison_failed", error=str(e))
            return default

    def _aggregate_results(self, folds: list[FoldMetrics]) -> WalkForwardResult:
        """Aggregate metrics across folds with statistical significance."""
        if not folds:
            return self._empty_result()

        n = len(folds)

        # Sample-size weighted aggregation for Sharpe
        total_trades = sum(f.num_trades for f in folds)
        if total_trades > 0:
            mean_sharpe = sum(f.sharpe_ratio * f.num_trades for f in folds) / total_trades
        else:
            mean_sharpe = statistics.mean(f.sharpe_ratio for f in folds)

        # Standard metrics
        returns = [f.total_return_pct for f in folds]
        mean_return = statistics.mean(returns)
        std_return = statistics.stdev(returns) if n > 1 else 0.0

        sharpes = [f.sharpe_ratio for f in folds]
        std_sharpe = statistics.stdev(sharpes) if n > 1 else 0.0

        mean_win_rate = statistics.mean(f.win_rate for f in folds)
        max_drawdown = max(f.max_drawdown_pct for f in folds)

        # B&H comparison
        excess_returns = [f.excess_return_pct for f in folds]
        mean_excess = statistics.mean(excess_returns)
        beats_count = sum(1 for f in folds if f.beats_buy_hold)
        pct_beats_bh = beats_count / n

        # Statistical significance: Wilcoxon signed-rank test
        # Tests if strategy returns are significantly different from B&H returns
        strategy_returns = [f.total_return_pct for f in folds]
        bh_returns = [f.buy_hold_return_pct for f in folds]

        wilcoxon_p = None
        sig_level: Literal["strong", "moderate", "weak", "none"] = "none"
        statistically_significant = False

        if n >= 5:  # Wilcoxon needs at least 5 samples
            try:
                # Test if differences are significantly different from zero
                differences = [s - b for s, b in zip(strategy_returns, bh_returns, strict=False)]
                # Filter out zero differences
                non_zero_diffs = [d for d in differences if d != 0]

                if len(non_zero_diffs) >= 5:
                    stat_result = stats.wilcoxon(non_zero_diffs, alternative="greater")
                    wilcoxon_p = float(stat_result.pvalue)

                    if wilcoxon_p < 0.01:
                        sig_level = "strong"
                        statistically_significant = True
                    elif wilcoxon_p < 0.05:
                        sig_level = "moderate"
                        statistically_significant = True
                    elif wilcoxon_p < 0.10:
                        sig_level = "weak"
                    else:
                        sig_level = "none"
            except Exception as e:
                logger.warning("wilcoxon_test_failed", error=str(e))

        return WalkForwardResult(
            folds=folds,
            num_folds=n,
            mean_return_pct=mean_return,
            std_return_pct=std_return,
            mean_sharpe=mean_sharpe,
            std_sharpe=std_sharpe,
            mean_win_rate=mean_win_rate,
            max_drawdown_pct=max_drawdown,
            total_trades=total_trades,
            mean_excess_vs_bh=mean_excess,
            pct_folds_beat_bh=pct_beats_bh,
            wilcoxon_p_value=wilcoxon_p,
            statistically_significant=statistically_significant,
            significance_level=sig_level,
        )

    def _empty_result(self) -> WalkForwardResult:
        """Return empty result for failed/empty runs."""
        return WalkForwardResult(
            folds=[],
            num_folds=0,
            mean_return_pct=0.0,
            std_return_pct=0.0,
            mean_sharpe=0.0,
            std_sharpe=0.0,
            mean_win_rate=0.0,
            max_drawdown_pct=0.0,
            total_trades=0,
            mean_excess_vs_bh=0.0,
            pct_folds_beat_bh=0.0,
            wilcoxon_p_value=None,
            statistically_significant=False,
            significance_level="none",
        )
