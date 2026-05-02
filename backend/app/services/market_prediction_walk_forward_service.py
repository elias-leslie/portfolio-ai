"""Historical walk-forward referee for market prediction research."""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass
from datetime import date
from statistics import NormalDist, mean
from typing import Literal

from app.constants import (
    CYCLICAL_SECTOR_SYMBOLS,
    DEFENSIVE_SECTOR_SYMBOLS,
    ETF_GROWTH,
    ETF_TOTAL_MARKET,
    MAG7_COMPONENT_SYMBOLS,
    PREDICTION_DRIVER_FEATURES,
    SECTOR_ETF_SYMBOLS,
)
from app.models.market_prediction import (
    MarketPredictionWalkForwardCandidateSummary,
    MarketPredictionWalkForwardScorecard,
)
from app.repositories.market_prediction_repository import MarketPredictionRepository
from app.storage import PortfolioStorage, get_storage

_TRAIN_WINDOW_DAYS = 504
_MIN_TRAIN_DAYS = 126
_ROUND_TRIP_COST_PCT = 0.05
_NEUTRAL_MOVE_BAND_PCT = 0.5
_MIN_TRADE_SHARE = 0.25
_REFEREE_ALPHA = 0.05
_MIN_BRIER_IMPROVEMENT_PCT = 1.0


@dataclass(frozen=True)
class _Candidate:
    candidate_id: str
    label: str
    mode: str
    lookback_days: int
    threshold_pct: float
    source_symbol: str | None = None
    feature_kind: Literal["absolute", "relative_to_target"] = "absolute"


@dataclass(frozen=True)
class _Observation:
    base_index: int
    target_index: int
    signal: int
    actual_move_pct: float
    trade_move_pct: float


def _candidate_grid(target_symbol: str) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for mode in ("trend", "reversion"):
        for lookback in (3, 5, 10, 20, 60):
            for threshold in (0.0, 0.25, 0.5):
                candidates.append(
                        _Candidate(
                            candidate_id=f"{mode}_{lookback}d_t{str(threshold).replace('.', '_')}",
                            label=_candidate_label(mode, lookback, threshold),
                            mode=mode,
                            lookback_days=lookback,
                            threshold_pct=threshold,
                        )
                )
    for source_symbol in PREDICTION_DRIVER_FEATURES:
        if source_symbol == target_symbol:
            continue
        source_slug = _slug(source_symbol)
        source_label = _label(source_symbol)
        for mode in ("trend", "reversion"):
            for lookback in (5, 20, 60):
                for threshold in (0.0, 0.5):
                    candidates.append(
                        _Candidate(
                            candidate_id=f"{source_slug}_{mode}_{lookback}d_t{str(threshold).replace('.', '_')}",
                            label=_candidate_label(f"{source_label} {mode}", lookback, threshold),
                            mode=mode,
                            lookback_days=lookback,
                            threshold_pct=threshold,
                            source_symbol=source_symbol,
                        )
                    )
                    candidates.append(
                        _Candidate(
                            candidate_id=(
                                f"{source_slug}_rel_{mode}_{lookback}d_t"
                                f"{str(threshold).replace('.', '_')}"
                            ),
                            label=_candidate_label(f"{source_label}/{target_symbol} {mode}", lookback, threshold),
                            mode=mode,
                            lookback_days=lookback,
                            threshold_pct=threshold,
                            source_symbol=source_symbol,
                            feature_kind="relative_to_target",
                        )
                    )
    return candidates


def _candidate_label(prefix: str, lookback: int, threshold: float) -> str:
    suffix = f" >{threshold:g}%" if threshold > 0 else ""
    return f"{prefix} {lookback}d{suffix}"


def _slug(value: str) -> str:
    return value.lower().replace("^", "").replace(".", "_").replace("-", "_")


def _label(value: str) -> str:
    labels = {
        "^VIX": "VIX",
        "^TNX": "10Y",
        "DX-Y.NYB": "DXY",
        "MAG7_EQ": "Mag7",
        "SECTOR_EQ": "Sectors",
        "CYCLICAL_DEFENSIVE": "Cyclicals/Defensives",
        "GROWTH_MARKET": "Growth/Market",
    }
    return labels.get(value, value)


def _driver_labels(target_symbol: str) -> list[str]:
    return [target_symbol, *[_label(source_symbol) for source_symbol in PREDICTION_DRIVER_FEATURES]]


class MarketPredictionWalkForwardService:
    """Run fixed-rule candidate searches against historical bars."""

    def __init__(
        self,
        *,
        repository: MarketPredictionRepository | None = None,
        storage: PortfolioStorage | None = None,
    ) -> None:
        self.storage = storage or get_storage()
        self.repository = repository or MarketPredictionRepository(self.storage)
        self._bar_cache: dict[str, list[tuple[date, float, float]]] = {}
        self._source_close_cache: dict[str, dict[date, float]] = {}

    def build_scorecard(
        self,
        *,
        symbol: str,
        window_days: int,
        min_sample_count: int,
        max_move_mae_pct: float,
    ) -> MarketPredictionWalkForwardScorecard:
        target_symbol = symbol.strip().upper()
        driver_labels = _driver_labels(target_symbol)
        bars = self._bars_for_research(target_symbol)
        min_train_samples = self._min_train_samples(window_days)
        if len(bars) < (min_train_samples * max(1, window_days)) + max(60, window_days) + 2:
            return MarketPredictionWalkForwardScorecard(
                status="insufficient",
                status_reason="Not enough historical bars for walk-forward test.",
                driver_labels=driver_labels,
                min_sample_count=min_sample_count,
                max_move_mae_pct=max_move_mae_pct,
                stride_days=max(1, window_days),
            )

        candidates = _candidate_grid(target_symbol)
        source_closes = self._load_source_closes(candidates, target_symbol=target_symbol)
        scorecards = [
            self._score_candidate(
                candidate,
                bars=bars,
                source_closes=source_closes,
                window_days=window_days,
                min_sample_count=min_sample_count,
                max_move_mae_pct=max_move_mae_pct,
                tested_candidates=len(candidates),
                min_train_samples=min_train_samples,
                driver_labels=driver_labels,
                target_symbol=target_symbol,
            )
            for candidate in candidates
        ]
        passing = [scorecard for scorecard in scorecards if scorecard.passed]
        if passing:
            selected = max(
                passing,
                key=lambda scorecard: (
                    scorecard.after_cost_edge_pct or -999.0,
                    -(scorecard.brier_score or 999.0),
                    scorecard.sample_count,
                ),
            )
            return self._with_top_candidates(selected, scorecards)
        selected = max(
            scorecards,
            key=lambda scorecard: (
                scorecard.after_cost_edge_pct or -999.0,
                scorecard.hit_rate_lcb or 0.0,
                -(scorecard.brier_score or 999.0),
            ),
        )
        return self._with_top_candidates(selected, scorecards)

    def _score_candidate(
        self,
        candidate: _Candidate,
        *,
        bars: list[tuple[date, float, float]],
        source_closes: dict[str, dict[date, float]],
        window_days: int,
        min_sample_count: int,
        max_move_mae_pct: float,
        tested_candidates: int,
        min_train_samples: int,
        driver_labels: list[str],
        target_symbol: str,
    ) -> MarketPredictionWalkForwardScorecard:
        closes = [row[2] for row in bars]
        observations = self._build_observations(
            candidate,
            bars=bars,
            closes=closes,
            source_closes=source_closes,
            window_days=window_days,
        )
        if len(observations) < min_sample_count:
            return self._candidate_scorecard(
                candidate,
                status="insufficient",
                status_reason=f"Need {min_sample_count} walk-forward samples; {len(observations)} available.",
                min_sample_count=min_sample_count,
                max_move_mae_pct=max_move_mae_pct,
                tested_candidates=tested_candidates,
                stride_days=max(1, window_days),
                driver_labels=driver_labels,
                target_symbol=target_symbol,
            )

        hits: list[bool] = []
        briers: list[float] = []
        baseline_briers: list[float] = []
        move_errors: list[float] = []
        baseline_move_errors: list[float] = []
        edge_samples: list[float] = []
        sample_dates: list[date] = []
        target_indices = [observation.target_index for observation in observations]
        up_prefix = [0.0]
        move_prefix = [0.0]
        signal_count_prefixes = {-1: [0], 0: [0], 1: [0]}
        signal_up_prefixes = {-1: [0.0], 0: [0.0], 1: [0.0]}
        signal_move_prefixes = {-1: [0.0], 0: [0.0], 1: [0.0]}
        for observation in observations:
            actual_up = 1.0 if observation.actual_move_pct > 0 else 0.0
            up_prefix.append(up_prefix[-1] + actual_up)
            move_prefix.append(move_prefix[-1] + observation.actual_move_pct)
            for signal in (-1, 0, 1):
                count_increment = 1 if observation.signal == signal else 0
                up_increment = actual_up if observation.signal == signal else 0.0
                move_increment = observation.actual_move_pct if observation.signal == signal else 0.0
                signal_count_prefixes[signal].append(signal_count_prefixes[signal][-1] + count_increment)
                signal_up_prefixes[signal].append(signal_up_prefixes[signal][-1] + up_increment)
                signal_move_prefixes[signal].append(signal_move_prefixes[signal][-1] + move_increment)
        for index, observation in enumerate(observations):
            train_window_samples = self._train_window_samples(window_days, min_train_samples)
            train_start = max(0, index - train_window_samples)
            train_end = bisect_left(target_indices, observation.base_index, 0, index)
            train_count = train_end - train_start
            if train_count < min_train_samples:
                continue
            signal = observation.signal
            same_signal_count = signal_count_prefixes[signal][train_end] - signal_count_prefixes[signal][train_start]
            if same_signal_count >= 20:
                reference_count = same_signal_count
                reference_up_sum = signal_up_prefixes[signal][train_end] - signal_up_prefixes[signal][train_start]
                reference_move_sum = signal_move_prefixes[signal][train_end] - signal_move_prefixes[signal][train_start]
            else:
                reference_count = train_count
                reference_up_sum = up_prefix[train_end] - up_prefix[train_start]
                reference_move_sum = move_prefix[train_end] - move_prefix[train_start]
            prob_up = self._clamp_probability(reference_up_sum / reference_count)
            expected_move_pct = reference_move_sum / reference_count
            baseline_prob_up = self._clamp_probability((up_prefix[train_end] - up_prefix[train_start]) / train_count)
            predicted_direction = self._direction_from_signal(observation.signal)
            hits.append(self._direction_hit(predicted_direction=predicted_direction, realized_move_pct=observation.actual_move_pct))
            actual_up = 1.0 if observation.actual_move_pct > 0 else 0.0
            briers.append((actual_up - prob_up) ** 2)
            baseline_briers.append((actual_up - baseline_prob_up) ** 2)
            move_errors.append(abs(observation.actual_move_pct - expected_move_pct))
            baseline_move_errors.append(abs(observation.actual_move_pct))
            sample_dates.append(bars[observation.base_index][0])
            if predicted_direction == "bullish":
                edge_samples.append(observation.trade_move_pct - _ROUND_TRIP_COST_PCT)
            elif predicted_direction == "bearish":
                edge_samples.append(-observation.trade_move_pct - _ROUND_TRIP_COST_PCT)

        if len(hits) < min_sample_count:
            return self._candidate_scorecard(
                candidate,
                status="insufficient",
                status_reason=f"Need {min_sample_count} trained walk-forward samples; {len(hits)} available.",
                min_sample_count=min_sample_count,
                max_move_mae_pct=max_move_mae_pct,
                tested_candidates=tested_candidates,
                stride_days=max(1, window_days),
                driver_labels=driver_labels,
                target_symbol=target_symbol,
            )

        sample_count = len(hits)
        hit_rate = mean(1.0 if hit else 0.0 for hit in hits)
        hit_rate_lcb = self._wilson_lower_bound(hit_rate, sample_count, tested_candidates)
        brier_score = mean(briers)
        baseline_brier_score = mean(baseline_briers)
        brier_improvement_pct = (
            ((baseline_brier_score - brier_score) / baseline_brier_score) * 100.0
            if baseline_brier_score > 0
            else None
        )
        move_mae_pct = mean(move_errors)
        baseline_move_mae_pct = mean(baseline_move_errors)
        after_cost_edge_pct = mean(edge_samples) if edge_samples else None
        min_trade_count = max(20, math.ceil(sample_count * _MIN_TRADE_SHARE))
        passed = (
            hit_rate_lcb > 0.5
            and brier_improvement_pct is not None
            and brier_improvement_pct >= _MIN_BRIER_IMPROVEMENT_PCT
            and move_mae_pct < baseline_move_mae_pct
            and move_mae_pct <= max_move_mae_pct
            and after_cost_edge_pct is not None
            and after_cost_edge_pct > 0
            and len(edge_samples) >= min_trade_count
        )
        status_reason = self._status_reason(
            passed=passed,
            hit_rate_lcb=hit_rate_lcb,
            brier_improvement_pct=brier_improvement_pct,
            move_mae_pct=move_mae_pct,
            baseline_move_mae_pct=baseline_move_mae_pct,
            max_move_mae_pct=max_move_mae_pct,
            after_cost_edge_pct=after_cost_edge_pct,
            trade_count=len(edge_samples),
            min_trade_count=min_trade_count,
        )
        return MarketPredictionWalkForwardScorecard(
            status="pass" if passed else "fail",
            status_reason=status_reason,
            candidate_id=candidate.candidate_id,
            candidate_label=candidate.label,
            candidate_feature_kind=candidate.feature_kind,
            benchmark_symbol=target_symbol if candidate.feature_kind == "relative_to_target" else None,
            driver_labels=driver_labels,
            tested_candidates=tested_candidates,
            sample_count=sample_count,
            min_sample_count=min_sample_count,
            trade_count=len(edge_samples),
            start_date=sample_dates[0] if sample_dates else None,
            end_date=sample_dates[-1] if sample_dates else None,
            train_window_days=_TRAIN_WINDOW_DAYS,
            stride_days=max(1, window_days),
            hit_rate=hit_rate,
            hit_rate_lcb=hit_rate_lcb,
            brier_score=brier_score,
            baseline_brier_score=baseline_brier_score,
            brier_improvement_pct=brier_improvement_pct,
            move_mae_pct=move_mae_pct,
            baseline_move_mae_pct=baseline_move_mae_pct,
            max_move_mae_pct=max_move_mae_pct,
            after_cost_edge_pct=after_cost_edge_pct,
            passed=passed,
        )

    def _build_observations(
        self,
        candidate: _Candidate,
        *,
        bars: list[tuple[date, float, float]],
        closes: list[float],
        source_closes: dict[str, dict[date, float]],
        window_days: int,
    ) -> list[_Observation]:
        stride = max(1, window_days)
        start_index = candidate.lookback_days
        end_index = len(bars) - window_days
        observations: list[_Observation] = []
        for base_index in range(start_index, end_index, stride):
            target_index = base_index + window_days
            entry_index = base_index + 1
            if entry_index >= len(bars):
                continue
            prior_close = closes[base_index - candidate.lookback_days]
            source_symbol = candidate.source_symbol
            if source_symbol is not None:
                source_by_date = source_closes.get(source_symbol, {})
                prior_close = source_by_date.get(bars[base_index - candidate.lookback_days][0], 0.0)
                source_close = source_by_date.get(bars[base_index][0], 0.0)
            else:
                source_close = closes[base_index]
            if prior_close <= 0 or source_close <= 0:
                continue
            lookback_return_pct = ((source_close / prior_close) - 1.0) * 100.0
            if candidate.feature_kind == "relative_to_target":
                target_prior_close = closes[base_index - candidate.lookback_days]
                target_close = closes[base_index]
                if target_prior_close <= 0 or target_close <= 0:
                    continue
                target_return_pct = ((target_close / target_prior_close) - 1.0) * 100.0
                lookback_return_pct -= target_return_pct
            signal = self._signal(candidate, lookback_return_pct)
            actual_move_pct = ((closes[target_index] / closes[base_index]) - 1.0) * 100.0
            trade_move_pct = ((bars[target_index][2] / bars[entry_index][1]) - 1.0) * 100.0
            observations.append(
                _Observation(
                    base_index=base_index,
                    target_index=target_index,
                    signal=signal,
                    actual_move_pct=actual_move_pct,
                    trade_move_pct=trade_move_pct,
                )
            )
        return observations

    def _load_source_closes(self, candidates: list[_Candidate], *, target_symbol: str) -> dict[str, dict[date, float]]:
        result: dict[str, dict[date, float]] = {}
        for source_symbol in sorted({candidate.source_symbol for candidate in candidates if candidate.source_symbol is not None}):
            if source_symbol is None or source_symbol == target_symbol:
                continue
            result[source_symbol] = self._source_close_map(source_symbol)
        return result

    def _source_close_map(self, source_symbol: str) -> dict[date, float]:
        cached = self._source_close_cache.get(source_symbol)
        if cached is not None:
            return cached
        if source_symbol == "MAG7_EQ":
            result = self._equal_weight_index(tuple(MAG7_COMPONENT_SYMBOLS), min_components=6)
        elif source_symbol == "SECTOR_EQ":
            result = self._equal_weight_index(tuple(SECTOR_ETF_SYMBOLS), min_components=9)
        elif source_symbol == "CYCLICAL_DEFENSIVE":
            cyclicals = self._equal_weight_index(tuple(CYCLICAL_SECTOR_SYMBOLS), min_components=4)
            defensives = self._equal_weight_index(tuple(DEFENSIVE_SECTOR_SYMBOLS), min_components=3)
            result = self._ratio_index(cyclicals, defensives)
        elif source_symbol == "GROWTH_MARKET":
            result = self._ratio_index(
                self._raw_close_map(ETF_GROWTH),
                self._raw_close_map(ETF_TOTAL_MARKET),
            )
        else:
            result = self._raw_close_map(source_symbol)
        self._source_close_cache[source_symbol] = result
        return result

    def _bars_for_research(self, symbol: str) -> list[tuple[date, float, float]]:
        canonical_symbol = symbol.strip().upper()
        cached = self._bar_cache.get(canonical_symbol)
        if cached is None:
            cached = self.repository.list_day_bars_for_research(canonical_symbol)
            self._bar_cache[canonical_symbol] = cached
        return cached

    def _raw_close_map(self, symbol: str) -> dict[date, float]:
        return {row_date: close for row_date, _, close in self._bars_for_research(symbol)}

    def _equal_weight_index(self, symbols: tuple[str, ...], *, min_components: int) -> dict[date, float]:
        returns_by_date: dict[date, list[float]] = {}
        for symbol in symbols:
            rows = self._bars_for_research(symbol)
            for index in range(1, len(rows)):
                row_date = rows[index][0]
                prior_close = rows[index - 1][2]
                close = rows[index][2]
                if prior_close > 0 and close > 0:
                    returns_by_date.setdefault(row_date, []).append((close / prior_close) - 1.0)
        index_value = 100.0
        result: dict[date, float] = {}
        for row_date in sorted(returns_by_date):
            returns = returns_by_date[row_date]
            if len(returns) < min_components:
                continue
            index_value *= 1.0 + mean(returns)
            result[row_date] = index_value
        return result

    @staticmethod
    def _ratio_index(numerator: dict[date, float], denominator: dict[date, float]) -> dict[date, float]:
        result: dict[date, float] = {}
        for row_date in sorted(set(numerator) & set(denominator)):
            denominator_value = denominator[row_date]
            if denominator_value > 0:
                result[row_date] = (numerator[row_date] / denominator_value) * 100.0
        return result

    @staticmethod
    def _min_train_samples(window_days: int) -> int:
        return max(20, _MIN_TRAIN_DAYS // max(1, window_days))

    @staticmethod
    def _train_window_samples(window_days: int, min_train_samples: int) -> int:
        return max(min_train_samples, _TRAIN_WINDOW_DAYS // max(1, window_days))

    @staticmethod
    def _signal(candidate: _Candidate, lookback_return_pct: float) -> int:
        if abs(lookback_return_pct) < candidate.threshold_pct:
            return 0
        direction = 1 if lookback_return_pct > 0 else -1
        return direction if candidate.mode == "trend" else -direction

    @staticmethod
    def _direction_from_signal(signal: int) -> str:
        if signal > 0:
            return "bullish"
        if signal < 0:
            return "bearish"
        return "neutral"

    @staticmethod
    def _direction_hit(*, predicted_direction: str, realized_move_pct: float) -> bool:
        if predicted_direction == "bullish":
            return realized_move_pct > 0
        if predicted_direction == "bearish":
            return realized_move_pct < 0
        return abs(realized_move_pct) <= _NEUTRAL_MOVE_BAND_PCT

    @staticmethod
    def _clamp_probability(value: float) -> float:
        return min(0.95, max(0.05, value))

    @staticmethod
    def _wilson_lower_bound(hit_rate: float, sample_count: int, tested_candidates: int) -> float:
        p = min(1.0, max(0.0, hit_rate))
        z = NormalDist().inv_cdf(1.0 - (_REFEREE_ALPHA / max(1, tested_candidates)))
        denominator = 1.0 + (z * z / sample_count)
        center = p + (z * z / (2.0 * sample_count))
        margin = z * math.sqrt(((p * (1.0 - p)) + (z * z / (4.0 * sample_count))) / sample_count)
        return max(0.0, (center - margin) / denominator)

    @staticmethod
    def _status_reason(
        *,
        passed: bool,
        hit_rate_lcb: float,
        brier_improvement_pct: float | None,
        move_mae_pct: float,
        baseline_move_mae_pct: float,
        max_move_mae_pct: float,
        after_cost_edge_pct: float | None,
        trade_count: int,
        min_trade_count: int,
    ) -> str:
        reason = "Walk-forward failed fixed gates."
        if passed:
            reason = "Walk-forward passed after costs."
        elif hit_rate_lcb <= 0.5:
            reason = "Walk-forward hit rate is not far enough above a coin flip."
        elif brier_improvement_pct is None or brier_improvement_pct < _MIN_BRIER_IMPROVEMENT_PCT:
            reason = "Walk-forward probability error does not beat the baseline by 1%."
        elif move_mae_pct >= baseline_move_mae_pct:
            reason = "Walk-forward move error does not beat a zero-move baseline."
        elif move_mae_pct > max_move_mae_pct:
            reason = f"Walk-forward move error too high: {move_mae_pct:.2f}% > {max_move_mae_pct:.2f}%."
        elif after_cost_edge_pct is None or after_cost_edge_pct <= 0:
            reason = "Walk-forward edge is not positive after costs."
        elif trade_count < min_trade_count:
            reason = f"Walk-forward made too few trades: {trade_count}/{min_trade_count}."
        return reason

    @classmethod
    def _with_top_candidates(
        cls,
        selected: MarketPredictionWalkForwardScorecard,
        scorecards: list[MarketPredictionWalkForwardScorecard],
    ) -> MarketPredictionWalkForwardScorecard:
        ranked = sorted(scorecards, key=cls._scorecard_rank, reverse=True)[:5]
        return selected.model_copy(
            update={
                "top_candidates": [
                    MarketPredictionWalkForwardCandidateSummary(
                        candidate_id=scorecard.candidate_id,
                        candidate_label=scorecard.candidate_label,
                        candidate_feature_kind=scorecard.candidate_feature_kind,
                        benchmark_symbol=scorecard.benchmark_symbol,
                        status=scorecard.status,
                        status_reason=scorecard.status_reason,
                        sample_count=scorecard.sample_count,
                        hit_rate=scorecard.hit_rate,
                        hit_rate_lcb=scorecard.hit_rate_lcb,
                        brier_improvement_pct=scorecard.brier_improvement_pct,
                        move_mae_pct=scorecard.move_mae_pct,
                        baseline_move_mae_pct=scorecard.baseline_move_mae_pct,
                        after_cost_edge_pct=scorecard.after_cost_edge_pct,
                        passed=scorecard.passed,
                    )
                    for scorecard in ranked
                    if scorecard.candidate_id is not None
                ]
            }
        )

    @staticmethod
    def _scorecard_rank(scorecard: MarketPredictionWalkForwardScorecard) -> tuple[float, float, float, float, int]:
        return (
            1.0 if scorecard.passed else 0.0,
            scorecard.after_cost_edge_pct if scorecard.after_cost_edge_pct is not None else -999.0,
            scorecard.hit_rate_lcb or 0.0,
            scorecard.brier_improvement_pct if scorecard.brier_improvement_pct is not None else -999.0,
            scorecard.sample_count,
        )

    @staticmethod
    def _candidate_scorecard(
        candidate: _Candidate,
        *,
        status: Literal["pass", "fail", "insufficient"],
        status_reason: str,
        min_sample_count: int,
        max_move_mae_pct: float,
        tested_candidates: int,
        stride_days: int,
        driver_labels: list[str],
        target_symbol: str,
    ) -> MarketPredictionWalkForwardScorecard:
        return MarketPredictionWalkForwardScorecard(
            status=status,
            status_reason=status_reason,
            candidate_id=candidate.candidate_id,
            candidate_label=candidate.label,
            candidate_feature_kind=candidate.feature_kind,
            benchmark_symbol=target_symbol if candidate.feature_kind == "relative_to_target" else None,
            driver_labels=driver_labels,
            tested_candidates=tested_candidates,
            min_sample_count=min_sample_count,
            max_move_mae_pct=max_move_mae_pct,
            stride_days=stride_days,
        )
