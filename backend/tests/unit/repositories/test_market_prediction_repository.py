from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Generator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from tests.fixtures.conftest import TEST_DB_URL

from app.models.market_prediction import (
    CommitteeSeatVote,
    MarketPredictionCall,
    MarketPredictionClusterReview,
    MarketPredictionEvaluation,
    MarketPredictionRun,
    MarketPredictionSeatReview,
    MarketPredictionVoteEvaluation,
    PredictionDirection,
    PredictionSourceCluster,
)
from app.repositories.market_prediction_repository import MarketPredictionRepository
from app.storage.facade import PortfolioStorage


@pytest.fixture(scope="session", autouse=True)
def ensure_test_schema_up_to_date() -> None:
    backend_root = Path(__file__).resolve().parents[3]
    env = os.environ.copy()
    env["PORTFOLIO_DB_URL"] = TEST_DB_URL
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(backend_root / "alembic.ini"), "upgrade", "head"],
        cwd=backend_root,
        env=env,
        check=True,
    )


@pytest.fixture
def storage() -> PortfolioStorage:
    return PortfolioStorage()


@pytest.fixture(autouse=True)
def clean_prediction_tables(storage: PortfolioStorage) -> Generator[None]:
    with storage.connection() as conn:
        conn.execute(
            "TRUNCATE market_prediction_cluster_reviews, market_prediction_vote_evaluations, market_prediction_seat_reviews, market_prediction_evaluations, market_prediction_votes, market_prediction_calls, market_prediction_runs CASCADE"
        )
        conn.commit()
    yield
    with storage.connection() as conn:
        conn.execute(
            "TRUNCATE market_prediction_cluster_reviews, market_prediction_vote_evaluations, market_prediction_seat_reviews, market_prediction_evaluations, market_prediction_votes, market_prediction_calls, market_prediction_runs CASCADE"
        )
        conn.commit()



def _run(
    *,
    run_id: str,
    as_of_ts: datetime,
    window_days: int = 3,
    base_date: date = date(2026, 4, 20),
    target_date: date = date(2026, 4, 23),
) -> MarketPredictionRun:
    return MarketPredictionRun(
        id=run_id,
        generated_at=as_of_ts,
        as_of_ts=as_of_ts,
        window_days=window_days,
        base_date=base_date,
        target_date=target_date,
        target_universe=["SPY"],
        lead_symbol="SPY",
        lead_direction="neutral",
        lead_prob_up=0.5,
        lead_expected_move_pct=0.0,
        source_snapshot={},
        committee_summary={},
        metadata={},
    )



def _vote(*, seat_key: str = "macro", window_days: int = 3) -> CommitteeSeatVote:
    return CommitteeSeatVote(
        seat_key=seat_key,
        agent_slug=f"{seat_key}-agent",
        symbol="SPY",
        window_days=window_days,
        direction_label="bullish",
        prob_up=0.65,
        expected_move_pct=1.0,
        confidence_score=70.0,
        source_clusters=[],
        metadata={},
    )



def _call(
    *,
    call_id: str,
    symbol: str = "SPY",
    window_days: int = 3,
    direction_label: PredictionDirection = "neutral",
    expected_move_pct: float = 0.0,
    top_source_clusters: list[PredictionSourceCluster] | None = None,
    metadata: dict[str, object] | None = None,
) -> MarketPredictionCall:
    return MarketPredictionCall.model_construct(
        id=call_id,
        symbol=symbol,
        window_days=window_days,
        direction_label=direction_label,
        prob_up=0.5,
        expected_move_pct=expected_move_pct,
        top_source_clusters=top_source_clusters or [],
        metadata=metadata or {},
    )


def _insert_day_bar(storage: PortfolioStorage, *, symbol: str, day: date, open_price: float, close_price: float) -> None:
    high_price = max(open_price, close_price)
    low_price = min(open_price, close_price)
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO symbols (symbol, security_type, created_at)
            VALUES (%s, 'equity', NOW())
            ON CONFLICT (symbol) DO NOTHING
            """,
            [symbol],
        )
        conn.execute(
            """
            INSERT INTO day_bars (symbol, date, open, high, low, close, volume, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, date) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                source = EXCLUDED.source
            """,
            [symbol, day, open_price, high_price, low_price, close_price, 1000, "test"],
        )
        conn.commit()



def _seat_review(*, review_id: str, generated_at: datetime, as_of_ts: datetime, review_state: str, macro_weight: float) -> MarketPredictionSeatReview:
    return MarketPredictionSeatReview(
        id=review_id,
        generated_at=generated_at,
        as_of_ts=as_of_ts,
        window_days=3,
        review_state=review_state,
        seat_scorecards=[
            {
                "seat_key": "cross_asset",
                "prior_weight": 1 / 3,
                "effective_weight": round((1.0 - macro_weight - 0.25), 12),
                "sample_size": 6,
                "direction_hit_rate": 0.5,
                "move_mae_pct": 1.0,
                "brier_score": 0.2,
                "skill_score": 0.6,
                "recommended_action": "hold",
            },
            {
                "seat_key": "macro",
                "prior_weight": 1 / 3,
                "effective_weight": macro_weight,
                "sample_size": 6,
                "direction_hit_rate": 0.8,
                "move_mae_pct": 0.4,
                "brier_score": 0.08,
                "skill_score": 0.86,
                "recommended_action": "upweight",
            },
            {
                "seat_key": "risk",
                "prior_weight": 1 / 3,
                "effective_weight": 0.25,
                "sample_size": 6,
                "direction_hit_rate": 0.2,
                "move_mae_pct": 3.0,
                "brier_score": 0.6,
                "skill_score": 0.2,
                "recommended_action": "downweight",
            },
        ],
        review_summary={
            "generated_at": generated_at.isoformat(),
            "review_state": review_state,
            "drift_callouts": [],
            "top_upweighted": [],
            "top_downweighted": [],
        },
        metadata={
            "weighting_half_life_days": 20,
            "trailing_window_trading_days": 60,
            "backfill_run_limit": 120,
            "supported_windows": [1, 3, 7, 14],
        },
    )



def _cluster_review(*, review_id: str, generated_at: datetime, as_of_ts: datetime, review_state: str, macro_weight: float) -> MarketPredictionClusterReview:
    return MarketPredictionClusterReview(
        id=review_id,
        generated_at=generated_at,
        as_of_ts=as_of_ts,
        window_days=3,
        review_state=review_state,
        cluster_scorecards=[
            {
                "cluster": "price_structure_market_regime_breadth",
                "prior_weight": 24.0,
                "effective_weight": round((100.0 - macro_weight - 25.0 - 2.0), 12),
                "sample_size": 24,
                "direction_hit_rate": 0.5,
                "move_mae_pct": 1.0,
                "brier_score": 0.25,
                "skill_score": 0.625,
                "freshness": "fresh",
                "gate_state": "active",
                "recommended_action": "hold",
            },
            {
                "cluster": "sentiment_fear_greed",
                "prior_weight": 4.0,
                "effective_weight": 2.0,
                "sample_size": 24,
                "direction_hit_rate": 0.0,
                "move_mae_pct": 4.0,
                "brier_score": 1.0,
                "skill_score": 0.04,
                "freshness": "fresh",
                "gate_state": "downweighted",
                "recommended_action": "downweight",
            },
            {
                "cluster": "options_positioning",
                "prior_weight": 14.0,
                "effective_weight": 25.0,
                "sample_size": 24,
                "direction_hit_rate": 0.8,
                "move_mae_pct": 0.5,
                "brier_score": 0.12,
                "skill_score": 0.88,
                "freshness": "fresh",
                "gate_state": "active",
                "recommended_action": "hold",
            },
            {
                "cluster": "macro_calendar",
                "prior_weight": 12.0,
                "effective_weight": macro_weight,
                "sample_size": 24,
                "direction_hit_rate": 1.0,
                "move_mae_pct": 0.1,
                "brier_score": 0.01,
                "skill_score": 0.9768,
                "freshness": "fresh",
                "gate_state": "active",
                "recommended_action": "upweight",
            },
        ],
        review_summary={
            "generated_at": generated_at.isoformat(),
            "review_state": review_state,
            "drift_callouts": [],
            "top_upweighted": [],
            "top_downweighted": [],
        },
        metadata={
            "weighting_half_life_days": 20,
            "trailing_window_trading_days": 60,
            "freshness_factors": {
                "fresh": 1.0,
                "stale": 0.5,
                "missing": 0.0,
                "unknown": 0.25,
            },
            "supported_windows": [1, 3, 7, 14],
        },
    )



def test_upsert_vote_evaluation_replaces_same_vote_id(storage: PortfolioStorage) -> None:
    repo = MarketPredictionRepository(storage)
    run = _run(run_id="run-1", as_of_ts=datetime(2026, 4, 20, 22, 15, tzinfo=UTC))
    repo.create_run(run)
    repo.replace_votes_for_run(run.id, [_vote(seat_key="macro")])

    with storage.connection() as conn:
        vote_row = conn.execute("SELECT id FROM market_prediction_votes WHERE run_id = %s LIMIT 1", [run.id]).fetchone()
    assert vote_row is not None
    vote_id = vote_row[0]

    repo.upsert_vote_evaluation(
        MarketPredictionVoteEvaluation(
            vote_id=vote_id,
            evaluated_at=datetime(2026, 4, 23, 22, 5, tzinfo=UTC),
            seat_key="macro",
            symbol="SPY",
            window_days=3,
            base_close=500.0,
            target_close=510.0,
            realized_move_pct=2.0,
            direction_hit=True,
            move_abs_error_pct=1.0,
            brier_score=0.1225,
            metadata={"run_id": run.id, "base_date": "2026-04-20", "target_date": "2026-04-23"},
        )
    )
    repo.upsert_vote_evaluation(
        MarketPredictionVoteEvaluation(
            vote_id=vote_id,
            evaluated_at=datetime(2026, 4, 24, 22, 5, tzinfo=UTC),
            seat_key="macro",
            symbol="SPY",
            window_days=3,
            base_close=500.0,
            target_close=515.0,
            realized_move_pct=3.0,
            direction_hit=True,
            move_abs_error_pct=2.0,
            brier_score=0.05,
            metadata={"run_id": run.id, "base_date": "2026-04-20", "target_date": "2026-04-24"},
        )
    )

    rows = storage.query(
        "SELECT vote_id, target_close, realized_move_pct, brier_score, metadata FROM market_prediction_vote_evaluations WHERE vote_id = ?",
        [vote_id],
    )
    assert rows.height == 1
    row = rows.row(0, named=True)
    assert row["vote_id"] == vote_id
    assert row["target_close"] == pytest.approx(515.0)
    assert row["realized_move_pct"] == pytest.approx(3.0)
    assert row["brier_score"] == pytest.approx(0.05)
    assert row["metadata"] == {"run_id": run.id, "base_date": "2026-04-20", "target_date": "2026-04-24"}



def test_upsert_seat_review_preserves_stable_id_and_precedence(storage: PortfolioStorage) -> None:
    repo = MarketPredictionRepository(storage)
    as_of_ts = datetime(2026, 4, 23, 22, 15, tzinfo=UTC)

    first = _seat_review(
        review_id="seat-review:3:2026-04-23T22:15:00+00:00",
        generated_at=datetime(2026, 4, 23, 22, 15, tzinfo=UTC),
        as_of_ts=as_of_ts,
        review_state="warmup",
        macro_weight=1 / 3,
    )
    lower_precedence_retry = _seat_review(
        review_id="ignored-id",
        generated_at=datetime(2026, 4, 23, 22, 20, tzinfo=UTC),
        as_of_ts=as_of_ts,
        review_state="degraded",
        macro_weight=0.2,
    )
    higher_precedence_retry = _seat_review(
        review_id="replacement-id",
        generated_at=datetime(2026, 4, 23, 22, 25, tzinfo=UTC),
        as_of_ts=as_of_ts,
        review_state="live",
        macro_weight=0.45,
    )

    persisted_first = repo.upsert_seat_review(first)
    persisted_lower = repo.upsert_seat_review(lower_precedence_retry)
    persisted_higher = repo.upsert_seat_review(higher_precedence_retry)

    assert persisted_first.id == "seat-review:3:2026-04-23T22:15:00+00:00"
    assert persisted_lower.id == persisted_first.id
    assert persisted_lower.review_state == "warmup"
    assert persisted_higher.id == persisted_first.id
    assert persisted_higher.review_state == "live"

    rows = storage.query(
        "SELECT id, review_state, seat_scorecards FROM market_prediction_seat_reviews WHERE window_days = ? AND as_of_ts = ?",
        [3, as_of_ts],
    )
    assert rows.height == 1
    row = rows.row(0, named=True)
    assert row["id"] == persisted_first.id
    assert row["review_state"] == "live"
    assert row["seat_scorecards"][1]["seat_key"] == "macro"
    assert row["seat_scorecards"][1]["effective_weight"] == pytest.approx(0.45)



def test_list_latest_seat_reviews_prefers_newest_asof_even_if_degraded(storage: PortfolioStorage) -> None:
    repo = MarketPredictionRepository(storage)
    older = _seat_review(
        review_id="seat-review:3:2026-04-23T22:15:00+00:00",
        generated_at=datetime(2026, 4, 23, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 23, 22, 15, tzinfo=UTC),
        review_state="live",
        macro_weight=0.45,
    )
    newer = _seat_review(
        review_id="seat-review:3:2026-04-24T22:15:00+00:00",
        generated_at=datetime(2026, 4, 24, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 24, 22, 15, tzinfo=UTC),
        review_state="degraded",
        macro_weight=1 / 3,
    )

    repo.upsert_seat_review(older)
    repo.upsert_seat_review(newer)

    reviews = repo.list_latest_seat_reviews(window_days=3, limit=5)

    assert [review.id for review in reviews] == [newer.id, older.id]
    assert reviews[0].review_state == "degraded"



def test_list_vote_evaluation_backfill_candidates_returns_recent_mature_runs_only(storage: PortfolioStorage) -> None:
    repo = MarketPredictionRepository(storage)
    mature_run = _run(run_id="run-mature", as_of_ts=datetime(2026, 4, 20, 22, 15, tzinfo=UTC))
    too_old_run = _run(run_id="run-old", as_of_ts=datetime(2025, 9, 1, 22, 15, tzinfo=UTC))
    too_old_run.base_date = date(2025, 9, 1)
    too_old_run.target_date = date(2025, 9, 4)
    future_run = _run(run_id="run-future", as_of_ts=datetime(2026, 4, 25, 22, 15, tzinfo=UTC))
    future_run.base_date = date(2026, 4, 25)
    future_run.target_date = date(2026, 4, 28)

    for run in (mature_run, too_old_run, future_run):
        repo.create_run(run)
    repo.replace_votes_for_run(mature_run.id, [_vote(seat_key="macro")])
    repo.replace_votes_for_run(too_old_run.id, [_vote(seat_key="risk")])
    repo.replace_votes_for_run(future_run.id, [_vote(seat_key="cross_asset")])

    candidates = repo.list_vote_evaluation_backfill_candidates(
        window_days=3,
        effective_market_date=date(2026, 4, 23),
        run_limit=120,
        max_age_days=180,
    )

    assert len(candidates) == 1
    assert candidates[0].run_id == mature_run.id
    assert candidates[0].seat_key == "macro"



def test_list_due_evaluation_candidates_keeps_latest_symbol_cohort(storage: PortfolioStorage) -> None:
    repo = MarketPredictionRepository(storage)
    older_run = _run(run_id="run-older", as_of_ts=datetime(2026, 4, 20, 22, 15, tzinfo=UTC))
    newer_run = _run(run_id="run-newer", as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC))

    repo.create_run(older_run)
    repo.create_run(newer_run)
    repo.upsert_call(older_run.id, _call(call_id="call-older", symbol="SPY"))
    repo.upsert_call(newer_run.id, _call(call_id="call-newer", symbol="SPY"))

    candidates = repo.list_due_evaluation_candidates(as_of_date=date(2026, 4, 23), limit=10)

    assert [candidate.call.id for candidate in candidates] == ["call-newer"]
    assert candidates[0].base_date == date(2026, 4, 20)
    assert candidates[0].target_date == date(2026, 4, 23)



def test_get_scorecard_uses_latest_distinct_symbol_cohorts(storage: PortfolioStorage) -> None:
    repo = MarketPredictionRepository(storage)
    older_run = _run(run_id="run-score-older", as_of_ts=datetime(2026, 4, 20, 22, 15, tzinfo=UTC))
    newer_run = _run(run_id="run-score-newer", as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC))

    repo.create_run(older_run)
    repo.create_run(newer_run)
    repo.upsert_call(older_run.id, _call(call_id="call-spy-older", symbol="SPY"))
    repo.upsert_call(newer_run.id, _call(call_id="call-spy-newer", symbol="SPY"))
    repo.upsert_call(newer_run.id, _call(call_id="call-xlf", symbol="XLF"))
    repo.upsert_evaluation(
        MarketPredictionEvaluation(
            call_id="call-spy-older",
            evaluated_at=datetime(2026, 4, 23, 22, 5, tzinfo=UTC),
            base_close=500.0,
            target_close=505.0,
            realized_move_pct=1.0,
            direction_hit=True,
            move_abs_error_pct=0.1,
            brier_score=0.01,
            metadata={},
        )
    )
    repo.upsert_evaluation(
        MarketPredictionEvaluation(
            call_id="call-spy-newer",
            evaluated_at=datetime(2026, 4, 23, 22, 6, tzinfo=UTC),
            base_close=500.0,
            target_close=490.0,
            realized_move_pct=-2.0,
            direction_hit=False,
            move_abs_error_pct=2.0,
            brier_score=0.5,
            metadata={},
        )
    )
    repo.upsert_evaluation(
        MarketPredictionEvaluation(
            call_id="call-xlf",
            evaluated_at=datetime(2026, 4, 23, 22, 7, tzinfo=UTC),
            base_close=40.0,
            target_close=41.0,
            realized_move_pct=2.5,
            direction_hit=True,
            move_abs_error_pct=1.0,
            brier_score=0.2,
            metadata={},
        )
    )

    scorecard = repo.get_scorecard(3)

    assert scorecard is not None
    assert scorecard.sample_size == 2
    assert scorecard.direction_hit_rate == pytest.approx(0.5)
    assert scorecard.move_mae_pct == pytest.approx(1.5)
    assert scorecard.brier_score == pytest.approx(0.35)

    spy_scorecard = repo.get_scorecard(3, symbol="spy")

    assert spy_scorecard is not None
    assert spy_scorecard.sample_size == 1
    assert spy_scorecard.direction_hit_rate == pytest.approx(0.0)
    assert spy_scorecard.move_mae_pct == pytest.approx(2.0)
    assert spy_scorecard.brier_score == pytest.approx(0.5)


def test_get_after_cost_edge_pct_uses_directional_latest_symbol_cohorts(storage: PortfolioStorage) -> None:
    repo = MarketPredictionRepository(storage)
    symbol = "ZTEST_EDGE"
    bullish_run = _run(
        run_id="run-cost-bullish",
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        base_date=date(2026, 4, 20),
        target_date=date(2026, 4, 23),
    )
    bearish_run = _run(
        run_id="run-cost-bearish",
        as_of_ts=datetime(2026, 4, 24, 22, 15, tzinfo=UTC),
        base_date=date(2026, 4, 21),
        target_date=date(2026, 4, 24),
    )

    repo.create_run(bullish_run)
    repo.create_run(bearish_run)
    _insert_day_bar(storage, symbol=symbol, day=date(2026, 4, 21), open_price=100.0, close_price=100.2)
    _insert_day_bar(storage, symbol=symbol, day=date(2026, 4, 22), open_price=100.0, close_price=99.8)
    _insert_day_bar(storage, symbol=symbol, day=date(2026, 4, 23), open_price=100.5, close_price=101.0)
    _insert_day_bar(storage, symbol=symbol, day=date(2026, 4, 24), open_price=99.5, close_price=99.0)
    repo.upsert_call(
        bullish_run.id,
        _call(call_id="call-cost-bullish", symbol=symbol, direction_label="bullish"),
    )
    repo.upsert_call(
        bearish_run.id,
        _call(call_id="call-cost-bearish", symbol=symbol, direction_label="bearish"),
    )
    repo.upsert_call(
        bearish_run.id,
        _call(call_id="call-cost-other-symbol", symbol="XLF", direction_label="bullish"),
    )
    repo.upsert_evaluation(
        MarketPredictionEvaluation(
            call_id="call-cost-bullish",
            evaluated_at=datetime(2026, 4, 23, 22, 6, tzinfo=UTC),
            base_close=500.0,
            target_close=502.0,
            realized_move_pct=0.4,
            direction_hit=True,
            move_abs_error_pct=0.1,
            brier_score=0.1,
            metadata={},
        )
    )
    repo.upsert_evaluation(
        MarketPredictionEvaluation(
            call_id="call-cost-bearish",
            evaluated_at=datetime(2026, 4, 24, 22, 6, tzinfo=UTC),
            base_close=502.0,
            target_close=500.5,
            realized_move_pct=-0.3,
            direction_hit=True,
            move_abs_error_pct=0.1,
            brier_score=0.1,
            metadata={},
        )
    )
    repo.upsert_evaluation(
        MarketPredictionEvaluation(
            call_id="call-cost-other-symbol",
            evaluated_at=datetime(2026, 4, 24, 22, 7, tzinfo=UTC),
            base_close=40.0,
            target_close=38.0,
            realized_move_pct=-5.0,
            direction_hit=False,
            move_abs_error_pct=5.0,
            brier_score=0.6,
            metadata={},
        )
    )

    edge = repo.get_after_cost_edge_pct(window_days=3, symbol=symbol.lower(), round_trip_cost_pct=0.05)

    assert edge == pytest.approx(0.95)
    assert repo.get_after_cost_edge_pct(window_days=3, symbol="XLK") is None


def test_list_day_bars_for_research_returns_latest_window_in_ascending_order(storage: PortfolioStorage) -> None:
    repo = MarketPredictionRepository(storage)
    symbol = "ZTEST_RESEARCH_BARS"
    _insert_day_bar(storage, symbol=symbol, day=date(2026, 1, 1), open_price=99.0, close_price=100.0)
    _insert_day_bar(storage, symbol=symbol, day=date(2026, 1, 2), open_price=100.0, close_price=101.0)
    _insert_day_bar(storage, symbol=symbol, day=date(2026, 1, 3), open_price=101.0, close_price=102.0)
    _insert_day_bar(storage, symbol=symbol, day=date(2026, 1, 4), open_price=102.0, close_price=103.0)

    bars = repo.list_day_bars_for_research(symbol.lower(), limit=2)

    assert bars == [
        (date(2026, 1, 3), 101.0, 102.0),
        (date(2026, 1, 4), 102.0, 103.0),
    ]



def test_list_vote_evaluations_for_weighting_keeps_latest_seat_symbol_cohort(storage: PortfolioStorage) -> None:
    repo = MarketPredictionRepository(storage)
    older_run = _run(run_id="run-weight-older", as_of_ts=datetime(2026, 4, 20, 22, 15, tzinfo=UTC))
    newer_run = _run(run_id="run-weight-newer", as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC))

    repo.create_run(older_run)
    repo.create_run(newer_run)
    repo.replace_votes_for_run(older_run.id, [_vote(seat_key="macro")])
    repo.replace_votes_for_run(newer_run.id, [_vote(seat_key="macro")])

    with storage.connection() as conn:
        older_vote_row = conn.execute("SELECT id FROM market_prediction_votes WHERE run_id = %s LIMIT 1", [older_run.id]).fetchone()
        newer_vote_row = conn.execute("SELECT id FROM market_prediction_votes WHERE run_id = %s LIMIT 1", [newer_run.id]).fetchone()
    assert older_vote_row is not None
    assert newer_vote_row is not None
    older_vote_id = older_vote_row[0]
    newer_vote_id = newer_vote_row[0]

    repo.upsert_vote_evaluation(
        MarketPredictionVoteEvaluation(
            vote_id=older_vote_id,
            evaluated_at=datetime(2026, 4, 23, 22, 5, tzinfo=UTC),
            seat_key="macro",
            symbol="SPY",
            window_days=3,
            base_close=500.0,
            target_close=505.0,
            realized_move_pct=1.0,
            direction_hit=True,
            move_abs_error_pct=0.5,
            brier_score=0.1,
            metadata={"run_id": older_run.id, "base_date": "2026-04-20", "target_date": "2026-04-23"},
        )
    )
    repo.upsert_vote_evaluation(
        MarketPredictionVoteEvaluation(
            vote_id=newer_vote_id,
            evaluated_at=datetime(2026, 4, 23, 22, 6, tzinfo=UTC),
            seat_key="macro",
            symbol="SPY",
            window_days=3,
            base_close=500.0,
            target_close=495.0,
            realized_move_pct=-1.0,
            direction_hit=False,
            move_abs_error_pct=1.5,
            brier_score=0.4,
            metadata={"run_id": newer_run.id, "base_date": "2026-04-20", "target_date": "2026-04-23"},
        )
    )

    evaluations = repo.list_vote_evaluations_for_weighting(window_days=3, effective_market_date=date(2026, 4, 23))

    assert [evaluation.vote_id for evaluation in evaluations] == [newer_vote_id]
    assert evaluations[0].direction_hit is False



def test_upsert_cluster_review_preserves_stable_id_and_precedence(storage: PortfolioStorage) -> None:
    repo = MarketPredictionRepository(storage)
    as_of_ts = datetime(2026, 4, 23, 22, 15, tzinfo=UTC)

    first = _cluster_review(
        review_id="cluster-review:3:2026-04-23T22:15:00+00:00",
        generated_at=datetime(2026, 4, 23, 22, 15, tzinfo=UTC),
        as_of_ts=as_of_ts,
        review_state="warmup",
        macro_weight=25.0,
    )
    lower_precedence_retry = _cluster_review(
        review_id="ignored-id",
        generated_at=datetime(2026, 4, 23, 22, 20, tzinfo=UTC),
        as_of_ts=as_of_ts,
        review_state="degraded",
        macro_weight=20.0,
    )
    same_precedence_same_ts = _cluster_review(
        review_id="different-but-ignored",
        generated_at=datetime(2026, 4, 23, 22, 15, tzinfo=UTC),
        as_of_ts=as_of_ts,
        review_state="warmup",
        macro_weight=40.0,
    )
    higher_precedence_retry = _cluster_review(
        review_id="replacement-id",
        generated_at=datetime(2026, 4, 23, 22, 25, tzinfo=UTC),
        as_of_ts=as_of_ts,
        review_state="live",
        macro_weight=41.0,
    )

    persisted_first = repo.upsert_cluster_review(first)
    persisted_lower = repo.upsert_cluster_review(lower_precedence_retry)
    persisted_same = repo.upsert_cluster_review(same_precedence_same_ts)
    persisted_higher = repo.upsert_cluster_review(higher_precedence_retry)

    assert persisted_first.id == "cluster-review:3:2026-04-23T22:15:00+00:00"
    assert persisted_lower.id == persisted_first.id
    assert persisted_lower.review_state == "warmup"
    assert persisted_same.id == persisted_first.id
    assert persisted_same.review_state == "warmup"
    assert persisted_higher.id == persisted_first.id
    assert persisted_higher.review_state == "live"

    rows = storage.query(
        "SELECT id, review_state, cluster_scorecards FROM market_prediction_cluster_reviews WHERE window_days = ? AND as_of_ts = ?",
        [3, as_of_ts],
    )
    assert rows.height == 1
    row = rows.row(0, named=True)
    assert row["id"] == persisted_first.id
    assert row["review_state"] == "live"
    assert row["cluster_scorecards"][3]["cluster"] == "macro_calendar"
    assert row["cluster_scorecards"][3]["effective_weight"] == pytest.approx(41.0)



def test_list_latest_cluster_reviews_prefers_newest_asof_even_if_degraded(storage: PortfolioStorage) -> None:
    repo = MarketPredictionRepository(storage)
    older = _cluster_review(
        review_id="cluster-review:3:2026-04-23T22:15:00+00:00",
        generated_at=datetime(2026, 4, 23, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 23, 22, 15, tzinfo=UTC),
        review_state="live",
        macro_weight=41.0,
    )
    newer = _cluster_review(
        review_id="cluster-review:3:2026-04-24T22:15:00+00:00",
        generated_at=datetime(2026, 4, 24, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 24, 22, 15, tzinfo=UTC),
        review_state="degraded",
        macro_weight=25.0,
    )

    repo.upsert_cluster_review(older)
    repo.upsert_cluster_review(newer)

    reviews = repo.list_latest_cluster_reviews(window_days=3, limit=5)

    assert [review.id for review in reviews] == [newer.id, older.id]
    assert reviews[0].review_state == "degraded"



def test_cluster_review_migration_creates_expected_constraints(storage: PortfolioStorage) -> None:
    constraint_rows = storage.query(
        """
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'market_prediction_cluster_reviews'::regclass
        ORDER BY conname ASC
        """,
    )
    names = [row[0] for row in constraint_rows.iter_rows()]

    index_rows = storage.query(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'market_prediction_cluster_reviews'
        ORDER BY indexname ASC
        """,
    )
    index_names = [row[0] for row in index_rows.iter_rows()]

    assert "ck_market_prediction_cluster_reviews_review_state" in names
    assert "ck_market_prediction_cluster_reviews_window_days" in names
    assert "uq_market_prediction_cluster_reviews_window_asof" in names
    assert "idx_market_prediction_cluster_reviews_window_generated" in index_names



def test_list_cluster_evaluation_samples_prefers_active_cluster_keys_then_top_source_clusters(storage: PortfolioStorage) -> None:
    repo = MarketPredictionRepository(storage)
    run = _run(run_id="run-clusters", as_of_ts=datetime(2026, 4, 23, 22, 15, tzinfo=UTC))
    repo.create_run(run)
    call_with_metadata = MarketPredictionCall.model_construct(
        id="call-metadata",
        symbol="SPY",
        window_days=3,
        direction_label="neutral",
        prob_up=0.5,
        expected_move_pct=0.0,
        top_source_clusters=[PredictionSourceCluster(cluster="sentiment")],
        metadata={"active_cluster_keys": [" Macro_Calendar ", "market_regime", "macro_calendar", "unsupported"]},
    )
    call_with_fallback = MarketPredictionCall.model_construct(
        id="call-fallback",
        symbol="XLF",
        window_days=3,
        direction_label="neutral",
        prob_up=0.5,
        expected_move_pct=0.0,
        top_source_clusters=[
            PredictionSourceCluster(cluster=" sentiment "),
            PredictionSourceCluster(cluster=""),
            PredictionSourceCluster(cluster="macro_calendar"),
        ],
        metadata={},
    )
    repo.upsert_call(run.id, call_with_metadata)
    repo.upsert_call(run.id, call_with_fallback)
    repo.upsert_evaluation(
        MarketPredictionEvaluation(
            call_id="call-metadata",
            evaluated_at=datetime(2026, 4, 24, 22, 5, tzinfo=UTC),
            base_close=500.0,
            target_close=505.0,
            realized_move_pct=1.0,
            direction_hit=True,
            move_abs_error_pct=0.5,
            brier_score=0.12,
            metadata={},
        )
    )
    repo.upsert_evaluation(
        MarketPredictionEvaluation(
            call_id="call-fallback",
            evaluated_at=datetime(2026, 4, 24, 22, 6, tzinfo=UTC),
            base_close=500.0,
            target_close=495.0,
            realized_move_pct=-1.0,
            direction_hit=False,
            move_abs_error_pct=1.5,
            brier_score=0.22,
            metadata={},
        )
    )

    samples = repo.list_cluster_evaluation_samples(window_days=3, effective_market_date=date(2026, 4, 24))
    by_call = {sample.call_id: sample for sample in samples}

    assert by_call["call-metadata"].active_cluster_keys == [
        "macro_calendar",
        "price_structure_market_regime_breadth",
    ]
    assert by_call["call-fallback"].active_cluster_keys == ["sentiment_fear_greed", "macro_calendar"]



def test_list_cluster_evaluation_samples_keeps_latest_symbol_cohort_and_filters_untrusted_fallback_clusters(storage: PortfolioStorage) -> None:
    repo = MarketPredictionRepository(storage)
    older_run = _run(run_id="run-clusters-older", as_of_ts=datetime(2026, 4, 20, 22, 15, tzinfo=UTC))
    newer_run = _run(run_id="run-clusters-newer", as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC))

    repo.create_run(older_run)
    repo.create_run(newer_run)
    repo.upsert_call(
        older_run.id,
        _call(
            call_id="call-trusted",
            symbol="SPY",
            top_source_clusters=[PredictionSourceCluster(cluster="market_regime", freshness="fresh")],
            metadata={"active_cluster_keys": ["market_regime"]},
        ),
    )
    repo.upsert_call(
        newer_run.id,
        _call(
            call_id="call-untrusted",
            symbol="SPY",
            top_source_clusters=[
                PredictionSourceCluster(
                    cluster="macro_calendar",
                    freshness="stale",
                    note="Derived fallback; tracked not ranked.",
                ),
                PredictionSourceCluster(
                    cluster="market_regime",
                    freshness="fresh",
                    note="Derived fallback; tracked not ranked.",
                ),
            ],
            metadata={"active_cluster_keys": ["macro_calendar", "market_regime"]},
        ),
    )
    repo.upsert_evaluation(
        MarketPredictionEvaluation(
            call_id="call-trusted",
            evaluated_at=datetime(2026, 4, 23, 22, 5, tzinfo=UTC),
            base_close=500.0,
            target_close=505.0,
            realized_move_pct=1.0,
            direction_hit=True,
            move_abs_error_pct=0.5,
            brier_score=0.12,
            metadata={},
        )
    )
    repo.upsert_evaluation(
        MarketPredictionEvaluation(
            call_id="call-untrusted",
            evaluated_at=datetime(2026, 4, 23, 22, 6, tzinfo=UTC),
            base_close=500.0,
            target_close=495.0,
            realized_move_pct=-1.0,
            direction_hit=False,
            move_abs_error_pct=1.5,
            brier_score=0.22,
            metadata={},
        )
    )

    samples = repo.list_cluster_evaluation_samples(window_days=3, effective_market_date=date(2026, 4, 24))

    assert len(samples) == 1
    assert samples[0].call_id == "call-untrusted"
    assert samples[0].active_cluster_keys == []
