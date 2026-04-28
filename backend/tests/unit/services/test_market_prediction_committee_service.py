"""Unit tests for the market prediction committee service."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.constants import PREDICTION_TARGET_SYMBOLS
from app.models.market_prediction import (
    CommitteeSeatVote,
    MarketPredictionCall,
    MarketPredictionClusterReview,
    MarketPredictionCommitteeResponse,
    MarketPredictionSeatReview,
)
from app.services.market_prediction_committee_service import MarketPredictionCommitteeService


class _FakeRepo:
    def __init__(self) -> None:
        self.snapshot: MarketPredictionCommitteeResponse | None = None
        self.raise_on_get = False
        self.raise_on_persist = False
        self.runs: list[Any] = []
        self.calls: list[MarketPredictionCall] = []
        self.votes: list[CommitteeSeatVote] = []
        self.history: list[MarketPredictionCall] = []
        self.scorecard: Any = None
        self.last_evaluated_at: datetime | None = None

    def get_latest_committee_snapshot(self, window_days: int) -> MarketPredictionCommitteeResponse | None:
        if self.raise_on_get:
            raise RuntimeError("boom")
        if self.snapshot and self.snapshot.window_days == window_days:
            return self.snapshot
        return None

    def persist_snapshot(
        self,
        *,
        run: Any,
        calls: list[MarketPredictionCall],
        votes: list[CommitteeSeatVote],
    ) -> None:
        if self.raise_on_persist:
            raise RuntimeError("persist failed")
        self.runs.append(run)
        self.calls = list(calls)
        self.votes = list(votes)

    def create_run(self, run: Any) -> None:
        self.runs.append(run)

    def upsert_call(self, run_id: str, call: MarketPredictionCall) -> None:
        self.calls.append(call)

    def replace_votes_for_run(self, run_id: str, votes: list[CommitteeSeatVote]) -> None:
        self.votes = list(votes)

    def list_history(self, symbol: str, window_days: int, limit: int = 30) -> list[MarketPredictionCall]:
        return self.history[:limit]

    def get_scorecard(self, window_days: int) -> Any:
        return self.scorecard

    def get_last_evaluated_at(self, window_days: int) -> datetime | None:
        return self.last_evaluated_at


class _FakeRoundtableClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.call_kwargs: dict[str, Any] | None = None
        self.closed = False

    def run_committee_roundtable(self, **kwargs: Any) -> dict[str, Any]:
        self.call_kwargs = kwargs
        return self.payload

    def close(self) -> None:
        self.closed = True


class _FakeRows:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def iter_rows(self, *, named: bool = False):
        assert named is True
        return iter(self._rows)


class _FakeStorage:
    def __init__(self, *, latest_closes: list[dict[str, Any]] | None = None) -> None:
        self.latest_closes = latest_closes or []

    def get_fear_greed_latest(self):
        return None

    def query(self, query: str, params: Any | None = None) -> _FakeRows:
        if "FROM day_bars" in query and "SELECT DISTINCT ON (symbol)" in query:
            return _FakeRows(self.latest_closes)
        return _FakeRows([])


def test_default_roster_mode_ignores_statistical_baseline_and_provider() -> None:
    service = MarketPredictionCommitteeService(repository=_FakeRepo())
    executed_seats = service._normalize_executed_seats(
        [
            {
                "seat_key": "baseline",
                "agent_slug": "statistical-baseline",
                "provider": "portfolio-ai",
                "model_id": "statistical-baseline-v1",
            },
            {
                "seat_key": "cross_asset",
                "agent_slug": "equity-analyst",
                "provider": "other-provider",
                "model_id": "grok-4.20-reasoning",
            },
            {
                "seat_key": "macro",
                "agent_slug": "market-pulse-analyst",
                "provider": "codex",
                "model_id": "gpt-5.4",
            },
            {
                "seat_key": "risk",
                "agent_slug": "risk-manager",
                "provider": "anthropic",
                "model_id": "claude-opus-4-7",
            },
        ]
    )

    assert service._classify_roster_mode(executed_seats) == "default_roster"
    assert service._classify_roster_mode(executed_seats[1:]) == "default_roster"

    custom_seats = [dict(seat) for seat in executed_seats[1:]]
    custom_seats[0]["model_id"] = "other-model"
    assert service._classify_roster_mode(custom_seats) == "custom_roster"


def _call(
    *,
    symbol: str = "SPY",
    window_days: int = 3,
    clusters: Any | None = None,
) -> MarketPredictionCall:
    return MarketPredictionCall.model_construct(
        symbol=symbol,
        window_days=window_days,
        direction_label="neutral",
        prob_up=0.5,
        expected_move_pct=0.0,
        confidence_score=40.0,
        top_source_clusters=[] if clusters is None else clusters,
        metadata={},
    )


def _response(
    *,
    lead_call: Any,
    calls: list[Any],
    source_snapshot: Any = None,
    scorecard: Any = None,
    committee_summary: Any = None,
    generated_at: datetime | None = None,
    as_of_ts: datetime | None = None,
    target_date: date | None = None,
    last_evaluated_at: datetime | None = None,
) -> MarketPredictionCommitteeResponse:
    response = MarketPredictionCommitteeResponse.model_construct(
        as_of_ts=as_of_ts or datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        generated_at=generated_at or datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        window_days=3,
        base_date=date(2026, 4, 21),
        target_date=target_date or date(2026, 4, 24),
        target_universe=PREDICTION_TARGET_SYMBOLS,
        lead_call=lead_call,
        calls=calls,
        votes=[],
        scorecard=scorecard,
        committee_summary={} if committee_summary is None else committee_summary,
        source_snapshot={} if source_snapshot is None else source_snapshot,
        last_evaluated_at=last_evaluated_at,
    )
    response._storage_metadata = {}
    return response


def _fresh_latest_closes(as_of_date: date = date(2026, 4, 21)) -> dict[str, dict[str, object]]:
    return {
        symbol: {"date": as_of_date.isoformat(), "close": 100.0 + index}
        for index, symbol in enumerate(PREDICTION_TARGET_SYMBOLS)
    }


def _fresh_source_snapshot(
    *,
    as_of_date: date = date(2026, 4, 21),
    clusters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot_clusters: dict[str, Any] = {
        "market_regime": {
            "freshness": "fresh",
            "latest_closes": _fresh_latest_closes(as_of_date),
        },
        "options_positioning": {
            "freshness": "fresh",
            "as_of_date": as_of_date.isoformat(),
            "call_pct": 0.54,
            "near_term_pct": 0.45,
            "concentration_pct": 0.15,
        },
        "macro_calendar": {
            "freshness": "fresh",
            "reason": "ok",
            "upcoming_event_count": 1,
            "next_event_date": "2026-04-22",
        },
    }
    if clusters:
        snapshot_clusters.update(clusters)
    return {
        "target_universe": PREDICTION_TARGET_SYMBOLS,
        "clusters": snapshot_clusters,
    }


def test_get_committee_snapshot_freezes_truth_contract_baseline(monkeypatch) -> None:
    repo = _FakeRepo()
    repo.snapshot = _response(
        lead_call=_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4}]),
        calls=[_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4}])],
        source_snapshot={"clusters": {" Macro_Calendar ": {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 2, "next_event_date": "2026-04-22"}}},
        committee_summary={"headline": "Constructive risk appetite"},
    )
    service = MarketPredictionCommitteeService(repository=repo)

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "fresh",
            "reason": "ok",
            "upcoming_event_count": 2,
            "next_event_date": "2026-04-22",
        },
    )

    result = service.get_committee_snapshot(window_days=3)

    assert result is not None
    assert result.source_snapshot["clusters"]["Macro_Calendar"] == {
        "freshness": "fresh",
        "reason": "ok",
        "upcoming_event_count": 2,
        "next_event_date": "2026-04-22",
    }
    assert result.committee_summary["truth_state"] == "pending_target"
    assert [cluster.cluster for cluster in result.lead_call.top_source_clusters] == ["market_regime"]



def test_get_committee_snapshot_defaults_additive_review_fields_for_legacy_rows(monkeypatch) -> None:
    repo = _FakeRepo()
    snapshot = _response(
        lead_call=_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4}]),
        calls=[_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4}])],
        source_snapshot={"clusters": {"macro_calendar": {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 1, "next_event_date": "2026-04-22"}}},
        committee_summary={"headline": "Legacy snapshot"},
    )
    snapshot._storage_metadata = {"committee_execution_path": "committee_endpoint", "executed_seats": []}
    repo.snapshot = snapshot
    service = MarketPredictionCommitteeService(repository=repo)

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "fresh",
            "reason": "ok",
            "upcoming_event_count": 1,
            "next_event_date": "2026-04-22",
        },
    )

    result = service.get_committee_snapshot(window_days=3)

    assert result is not None
    assert result.committee_summary["resolved_seat_weights"] == []
    assert result.committee_summary["review_state"] is None
    assert result.committee_summary["review_as_of_ts"] is None
    assert result.committee_summary["review_row_id"] is None



def test_normalize_response_marks_previous_session_snapshot_invalidated(monkeypatch) -> None:
    service = MarketPredictionCommitteeService(repository=_FakeRepo(), storage=_FakeStorage())
    snapshot = _response(
        lead_call=_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4}]),
        calls=[_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4}])],
        generated_at=datetime(2026, 4, 21, 20, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 21, 20, 15, tzinfo=UTC),
        source_snapshot={
            "clusters": {
                "market_regime": {
                    "latest_closes": _fresh_latest_closes(date(2026, 4, 21))
                },
                "options_positioning": {
                    "freshness": "fresh",
                    "as_of_date": "2026-04-21",
                },
                "macro_calendar": {
                    "freshness": "fresh",
                    "reason": "ok",
                    "upcoming_event_count": 2,
                    "next_event_date": "2026-04-23",
                },
            }
        },
        committee_summary={"headline": "Old snapshot"},
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **kwargs: kwargs.get("existing") or {},
    )

    result = service._normalize_response(
        snapshot,
        market_now=datetime(2026, 4, 22, 15, 0, tzinfo=UTC),
    )

    assert result.freshness_summary is not None
    assert result.freshness_summary.state == "invalid"
    assert result.freshness_summary.invalidated is True
    assert "previous_market_session" in result.freshness_summary.reason_codes
    assert result.freshness_summary.critical_clusters[0].cluster == "market_regime"
    assert result.freshness_summary.critical_clusters[0].freshness == "fresh"


def test_normalize_response_marks_waiting_after_close_invalidated_even_same_session(monkeypatch) -> None:
    service = MarketPredictionCommitteeService(repository=_FakeRepo(), storage=_FakeStorage())
    snapshot = _response(
        lead_call=_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4}]),
        calls=[_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4}])],
        target_date=date(2026, 4, 21),
        source_snapshot={
            "clusters": {
                "market_regime": {
                    "latest_closes": {
                        "SPY": {"date": "2026-04-21", "close": 500.0},
                    }
                },
                "options_positioning": {
                    "freshness": "fresh",
                    "as_of_date": "2026-04-21",
                },
                "macro_calendar": {
                    "freshness": "fresh",
                    "reason": "ok",
                    "upcoming_event_count": 1,
                    "next_event_date": "2026-04-22",
                },
            }
        },
        committee_summary={"headline": "Target passed"},
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **kwargs: kwargs.get("existing") or {},
    )

    result = service._normalize_response(
        snapshot,
        market_now=datetime(2026, 4, 21, 22, 45, tzinfo=UTC),
    )

    assert result.committee_summary["truth_state"] == "waiting_after_close"
    assert result.freshness_summary is not None
    assert result.freshness_summary.state == "invalid"
    assert result.freshness_summary.invalidated is True
    assert "target_reached_pending_evaluation" in result.freshness_summary.reason_codes
    assert result.freshness_summary.refresh_after_seconds == 60


def test_market_regime_freshness_requires_every_prediction_target() -> None:
    service = MarketPredictionCommitteeService(repository=_FakeRepo(), storage=_FakeStorage())

    cluster = service._normalize_market_regime_cluster(
        {
            "latest_closes": {
                "SPY": {"date": "2026-04-21", "close": 500.0},
            }
        },
        market_date=date(2026, 4, 21),
    )

    assert cluster["freshness"] == "missing"
    assert "XLK" in cluster["missing_symbols"]
    assert cluster["latest_common_date"] == "2026-04-21"


def test_market_regime_freshness_accepts_newer_session_prices() -> None:
    service = MarketPredictionCommitteeService(repository=_FakeRepo(), storage=_FakeStorage())

    cluster = service._normalize_market_regime_cluster(
        {
            "latest_closes": {
                symbol: {"date": "2026-04-28", "close": 100.0}
                for symbol in PREDICTION_TARGET_SYMBOLS
            }
        },
        market_date=date(2026, 4, 27),
    )

    assert cluster["freshness"] == "fresh"
    assert cluster["stale_symbols"] == []
    assert cluster["latest_common_date"] == "2026-04-28"


def test_mag7_sector_leadership_accepts_newer_session_prices(monkeypatch) -> None:
    service = MarketPredictionCommitteeService(repository=_FakeRepo())
    symbols = [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "META",
        "GOOGL",
        "TSLA",
        "XLK",
        "XLC",
        "XLY",
    ]

    def recent_closes(_symbols: list[str], **_: object) -> dict[str, list[tuple[date, float]]]:
        return {
            symbol: [(date(2026, 4, 28), 101.0), (date(2026, 4, 27), 100.0)]
            for symbol in symbols
        }

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 27),
    )
    monkeypatch.setattr(
        service,
        "_query_recent_closes",
        recent_closes,
        raising=False,
    )

    cluster = service._build_mag7_sector_leadership_cluster(
        as_of_ts=datetime(2026, 4, 28, 13, 0, tzinfo=UTC)
    )

    assert cluster["freshness"] == "fresh"
    assert cluster["missing_tickers"] == []
    assert cluster["latest_common_date"] == "2026-04-28"


def test_build_source_snapshot_adds_additive_indicator_sleeves(monkeypatch) -> None:
    service = MarketPredictionCommitteeService(
        repository=_FakeRepo(),
        storage=_FakeStorage(
            latest_closes=[
                {"symbol": "SPY", "date": date(2026, 4, 21), "close": 500.0},
                {"symbol": "XLK", "date": date(2026, 4, 21), "close": 210.0},
                {"symbol": "XLC", "date": date(2026, 4, 21), "close": 95.0},
                {"symbol": "XLY", "date": date(2026, 4, 21), "close": 180.0},
            ]
        ),
    )
    as_of_ts = datetime(2026, 4, 21, 22, 15, tzinfo=UTC)

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_latest_options_flow",
        lambda _storage: None,
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "fresh",
            "reason": "ok",
            "upcoming_event_count": 1,
            "next_event_date": "2026-04-22",
            "event_type_counts": {"cpi_release": 1},
            "high_impact_event_count": 1,
            "next_high_impact_event": {
                "event_type": "cpi_release",
                "event_date": "2026-04-22",
                "event_time": "08:30:00",
                "title": "CPI",
                "impact_score": 5,
            },
        },
    )
    monkeypatch.setattr(
        service,
        "_build_mag7_sector_leadership_cluster",
        lambda **_: {
            "freshness": "fresh",
            "mag7_tickers": ["AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA"],
            "available_tickers": ["AAPL", "MSFT", "NVDA", "AMZN"],
            "missing_tickers": ["META", "GOOGL", "TSLA"],
            "latest_common_date": "2026-04-21",
            "average_change_pct": 1.25,
            "leader_symbol": "NVDA",
            "leader_change_pct": 2.2,
            "laggard_symbol": "AAPL",
            "laggard_change_pct": 0.4,
            "sector_proxy_changes": {"XLK": 1.0, "XLC": 0.5, "XLY": 0.25},
            "note": None,
        },
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_build_overnight_premarket_afterhours_futures_news_cluster",
        lambda **_: {
            "freshness": "fresh",
            "market_status": "closed",
            "latest_market_news_at": "2026-04-21T21:00:00+00:00",
            "recent_market_news_count_24h": 3,
            "spy_latest_close_date": "2026-04-21",
            "spy_gap_proxy_pct": 0.8,
            "note": None,
        },
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_build_oil_shock_overlay_cluster",
        lambda **_: {
            "freshness": "missing",
            "gate_state": "missing",
            "canonical_series": "DCOILWTICO",
            "latest_observation_date": None,
            "latest_value": None,
            "prior_value": None,
            "daily_change_pct": None,
            "event_tags": [],
            "note": None,
        },
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_build_holiday_turn_of_month_cluster",
        lambda **_: {
            "freshness": "fresh",
            "gate_state": "off",
            "market_date": "2026-04-21",
            "is_first_three_trading_days": False,
            "is_last_two_trading_days": False,
            "is_pre_holiday_trading_day": False,
            "next_full_holiday_name": None,
            "note": None,
        },
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_build_day_of_week_cluster",
        lambda **_: {
            "freshness": "fresh",
            "gate_state": "tracked_only",
            "calendar_weekday": "tuesday",
            "trading_weekday": "tuesday",
            "is_trading_day": True,
            "note": None,
        },
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_build_freight_transport_event_cluster",
        lambda **_: {
            "freshness": "fresh",
            "gate_state": "tracked_only",
            "event_tags": [],
            "note": None,
        },
        raising=False,
    )

    result = service.build_source_snapshot(as_of_ts)

    assert result["clusters"]["mag7_sector_leadership"]["leader_symbol"] == "NVDA"
    assert result["clusters"]["overnight_premarket_afterhours_futures_news"]["recent_market_news_count_24h"] == 3
    assert result["clusters"]["oil_shock_overlay"]["canonical_series"] == "DCOILWTICO"
    assert result["clusters"]["holiday_turn_of_month"]["gate_state"] == "off"
    assert result["clusters"]["day_of_week"]["gate_state"] == "tracked_only"
    assert result["clusters"]["freight_transport_event"]["gate_state"] == "tracked_only"
    assert result["clusters"]["macro_calendar"]["event_type_counts"] == {"cpi_release": 1}



def test_build_day_of_week_cluster_marks_non_trading_days_missing(monkeypatch) -> None:
    service = MarketPredictionCommitteeService(repository=_FakeRepo())
    as_of_ts = datetime(2026, 7, 4, 14, 0, tzinfo=UTC)

    monkeypatch.setattr("app.services.market_prediction_committee_service.is_trading_day", lambda *_args, **_kwargs: False)

    cluster = service._build_day_of_week_cluster(as_of_ts=as_of_ts)

    assert cluster == {
        "freshness": "missing",
        "gate_state": "tracked_only",
        "calendar_weekday": "saturday",
        "trading_weekday": None,
        "is_trading_day": False,
        "note": None,
    }



def test_build_oil_shock_overlay_cluster_returns_missing_when_wti_unavailable(monkeypatch) -> None:
    service = MarketPredictionCommitteeService(repository=_FakeRepo())
    as_of_ts = datetime(2026, 4, 21, 22, 15, tzinfo=UTC)

    monkeypatch.setattr(
        service,
        "_load_oil_proxy_observations",
        lambda **_: [],
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_load_oil_observations",
        lambda **_: [],
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )

    cluster = service._build_oil_shock_overlay_cluster(as_of_ts=as_of_ts)

    assert cluster == {
        "freshness": "missing",
        "gate_state": "missing",
        "canonical_series": "DCOILWTICO",
        "source": "fred",
        "latest_observation_date": None,
        "latest_value": None,
        "prior_value": None,
        "daily_change_pct": None,
        "event_tags": [],
        "note": None,
    }


def test_build_oil_shock_overlay_cluster_does_not_activate_stale_wti(monkeypatch) -> None:
    service = MarketPredictionCommitteeService(repository=_FakeRepo())
    as_of_ts = datetime(2026, 4, 27, 13, 15, tzinfo=UTC)

    monkeypatch.setattr(
        service,
        "_load_oil_proxy_observations",
        lambda **_: [],
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_load_oil_observations",
        lambda **_: [(date(2026, 4, 20), 91.06), (date(2026, 4, 17), 85.91)],
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 27),
    )

    cluster = service._build_oil_shock_overlay_cluster(as_of_ts=as_of_ts)

    assert cluster["freshness"] == "stale"
    assert cluster["gate_state"] == "stale"
    assert cluster["source"] == "fred"
    assert cluster["daily_change_pct"] == pytest.approx(5.9946, rel=0.001)


def test_build_oil_shock_overlay_cluster_prefers_fresh_proxy(monkeypatch) -> None:
    service = MarketPredictionCommitteeService(repository=_FakeRepo())
    as_of_ts = datetime(2026, 4, 28, 13, 15, tzinfo=UTC)

    monkeypatch.setattr(
        service,
        "_load_oil_proxy_observations",
        lambda **_: [(date(2026, 4, 28), 91.0), (date(2026, 4, 27), 89.0)],
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_load_oil_observations",
        lambda **_: [(date(2026, 4, 20), 91.06), (date(2026, 4, 17), 85.91)],
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 27),
    )

    cluster = service._build_oil_shock_overlay_cluster(as_of_ts=as_of_ts)

    assert cluster["freshness"] == "fresh"
    assert cluster["gate_state"] == "active"
    assert cluster["canonical_series"] == "CL=F"
    assert cluster["source"] == "yfinance_day_bars"
    assert cluster["latest_observation_date"] == "2026-04-28"


def test_normalize_options_positioning_allows_newer_session_data() -> None:
    service = MarketPredictionCommitteeService(repository=_FakeRepo())

    current = service._normalize_options_positioning_cluster(
        {"as_of_date": "2026-04-28", "call_pct": 0.5},
        market_date=date(2026, 4, 27),
    )
    stale = service._normalize_options_positioning_cluster(
        {"as_of_date": "2026-04-24", "call_pct": 0.5},
        market_date=date(2026, 4, 27),
    )

    assert current["freshness"] == "fresh"
    assert stale["freshness"] == "stale"



def test_generate_snapshot_uses_weighted_committee_synthesis_and_additive_review_metadata(monkeypatch) -> None:
    repo = _FakeRepo()
    raw_payload = {
        "_portfolio_execution_path": "committee_endpoint",
        "calls": [],
        "votes": [
            {
                "seat_key": "macro",
                "agent_slug": "macro-analyst",
                "symbol": "SPY",
                "prob_up": 0.8,
                "expected_move_pct": 2.0,
                "confidence_score": 80,
                "source_clusters": [{"cluster": "macro_calendar", "weight": 0.6}],
            },
            {
                "seat_key": "risk",
                "agent_slug": "risk-manager",
                "symbol": "SPY",
                "prob_up": 0.4,
                "expected_move_pct": -1.0,
                "confidence_score": None,
                "source_clusters": [{"cluster": "market_regime", "weight": 0.4}],
            },
            {
                "seat_key": "new-seat",
                "agent_slug": "ignored-seat",
                "symbol": "SPY",
                "prob_up": 0.95,
                "expected_move_pct": 4.0,
                "confidence_score": 99,
                "source_clusters": [{"cluster": "market_regime", "weight": 0.9}],
            },
        ],
    }
    fake_client = _FakeRoundtableClient(raw_payload)
    review = MarketPredictionSeatReview(
        id="seat-review:3:2026-04-21T22:15:00+00:00",
        generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        window_days=3,
        review_state="live",
        seat_scorecards=[
            {
                "seat_key": "cross_asset",
                "prior_weight": 1 / 3,
                "effective_weight": 0.2,
                "sample_size": 6,
                "direction_hit_rate": 0.5,
                "move_mae_pct": 1.0,
                "brier_score": 0.2,
                "skill_score": 0.6,
                "recommended_action": "downweight",
            },
            {
                "seat_key": "macro",
                "prior_weight": 1 / 3,
                "effective_weight": 0.5,
                "sample_size": 12,
                "direction_hit_rate": 0.7,
                "move_mae_pct": 0.6,
                "brier_score": 0.12,
                "skill_score": 0.82,
                "recommended_action": "upweight",
            },
            {
                "seat_key": "risk",
                "prior_weight": 1 / 3,
                "effective_weight": 0.3,
                "sample_size": 10,
                "direction_hit_rate": 0.4,
                "move_mae_pct": 2.1,
                "brier_score": 0.35,
                "skill_score": 0.41,
                "recommended_action": "hold",
            },
        ],
        review_summary={
            "generated_at": "2026-04-21T22:15:00+00:00",
            "review_state": "live",
            "drift_callouts": ["macro gained weight versus prior"],
            "top_upweighted": [{"kind": "seat", "key": "macro", "prior_weight": 1 / 3, "effective_weight": 0.5}],
            "top_downweighted": [{"kind": "seat", "key": "cross_asset", "prior_weight": 1 / 3, "effective_weight": 0.2}],
        },
        metadata={
            "weighting_half_life_days": 20,
            "trailing_window_trading_days": 60,
            "backfill_run_limit": 120,
            "supported_windows": [1, 3, 7, 14],
        },
    )
    cluster_review = MarketPredictionClusterReview(
        id="cluster-review:3:2026-04-21T22:15:00+00:00",
        generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        window_days=3,
        review_state="live",
        cluster_scorecards=[
            {"cluster": "market_regime", "prior_weight": 0.25, "effective_weight": 0.32, "sample_size": 24, "direction_hit_rate": 0.6, "move_mae_pct": 0.9, "brier_score": 0.2, "skill_score": 0.7, "freshness": "fresh", "recommended_action": "upweight"},
            {"cluster": "sentiment", "prior_weight": 0.25, "effective_weight": 0.0, "sample_size": 0, "direction_hit_rate": None, "move_mae_pct": None, "brier_score": None, "skill_score": None, "freshness": "missing", "recommended_action": "downweight"},
            {"cluster": "options_positioning", "prior_weight": 0.25, "effective_weight": 0.28, "sample_size": 18, "direction_hit_rate": 0.7, "move_mae_pct": 0.5, "brier_score": 0.12, "skill_score": 0.83, "freshness": "fresh", "recommended_action": "hold"},
            {"cluster": "macro_calendar", "prior_weight": 0.25, "effective_weight": 0.40, "sample_size": 24, "direction_hit_rate": 1.0, "move_mae_pct": 0.1, "brier_score": 0.01, "skill_score": 0.98, "freshness": "fresh", "recommended_action": "upweight"},
        ],
        review_summary={"generated_at": "2026-04-21T22:15:00+00:00", "review_state": "live", "drift_callouts": [], "top_upweighted": [], "top_downweighted": []},
        metadata={
            "weighting_half_life_days": 20,
            "trailing_window_trading_days": 60,
            "freshness_factors": {"fresh": 1.0, "stale": 0.5, "missing": 0.0, "unknown": 0.25},
            "supported_windows": [1, 3, 7, 14],
        },
    )
    service = MarketPredictionCommitteeService(
        repository=repo,
        roundtable_client_factory=lambda **_: fake_client,
    )

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        service,
        "_build_source_snapshot",
        lambda _: _fresh_source_snapshot(),
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "fresh",
            "reason": "ok",
            "upcoming_event_count": 1,
            "next_event_date": "2026-04-22",
        },
    )
    monkeypatch.setattr(service, "_build_statistical_baseline_votes", lambda **_: [], raising=False)

    result = service.generate_snapshot(
        window_days=3,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        review=review,
        cluster_review=cluster_review,
    )

    assert repo.calls[0].prob_up == pytest.approx(0.6199584837)
    assert repo.calls[0].metadata["probability_calibration"]["raw_prob_up"] == pytest.approx(0.6713692625)
    assert repo.calls[0].expected_move_pct == pytest.approx(0.875)
    assert repo.calls[0].confidence_score == pytest.approx(35.0)
    assert repo.calls[0].confidence_band_low_pct == pytest.approx(-1.0)
    assert repo.calls[0].confidence_band_high_pct == pytest.approx(2.0)
    assert repo.calls[0].committee_disagreement_score == pytest.approx(0.4)
    assert repo.calls[0].metadata["publication_state"] == "no_edge"
    assert repo.calls[0].metadata["abstain_reason_codes"] == ["high_disagreement"]
    assert repo.calls[0].metadata["aggregation_mode"] == "weighted_committee"
    assert repo.calls[0].metadata["active_seat_keys"] == ["macro", "risk"]
    assert repo.calls[0].metadata["active_cluster_keys"] == ["macro_calendar", "market_regime"]
    assert [cluster.cluster for cluster in repo.calls[0].top_source_clusters] == ["macro_calendar", "market_regime"]
    assert [cluster.weight for cluster in repo.calls[0].top_source_clusters] == [pytest.approx(0.40), pytest.approx(0.32)]
    assert result.source_snapshot["clusters"]["macro_calendar"]["effective_weight"] == pytest.approx(0.40)
    assert result.source_snapshot["clusters"]["market_regime"]["effective_weight"] == pytest.approx(0.32)
    assert result.source_snapshot["clusters"].get("sentiment", {}).get("effective_weight") is None
    assert result.committee_summary["resolved_seat_weights"] == [
        {"seat_key": "cross_asset", "prior_weight": pytest.approx(1 / 3), "effective_weight": 0.2, "sample_size": 6, "skill_score": 0.6},
        {"seat_key": "macro", "prior_weight": pytest.approx(1 / 3), "effective_weight": 0.5, "sample_size": 12, "skill_score": 0.82},
        {"seat_key": "risk", "prior_weight": pytest.approx(1 / 3), "effective_weight": 0.3, "sample_size": 10, "skill_score": 0.41},
    ]
    assert result.committee_summary["review_state"] == "live"
    assert result.committee_summary["review_as_of_ts"] == "2026-04-21T22:15:00+00:00"
    assert result.committee_summary["review_row_id"] == "seat-review:3:2026-04-21T22:15:00+00:00"
    assert repo.runs[0].metadata["adaptive_weighting_version"] == "seat-v1"
    assert repo.runs[0].metadata["review_state"] == "live"
    assert repo.runs[0].metadata["review_row_id"] == "seat-review:3:2026-04-21T22:15:00+00:00"
    assert repo.runs[0].metadata["adaptive_cluster_weighting_version"] == "cluster-v1"
    assert repo.runs[0].metadata["cluster_review_state"] == "live"
    assert repo.runs[0].metadata["cluster_review_row_id"] == "cluster-review:3:2026-04-21T22:15:00+00:00"
    assert repo.runs[0].metadata["resolved_cluster_weights"][0]["cluster"] == "market_regime"
    assert repo.runs[0].metadata["resolved_cluster_weights"][3]["cluster"] == "macro_calendar"


def test_generate_snapshot_fact_check_blocks_stale_target_prices(monkeypatch) -> None:
    repo = _FakeRepo()
    raw_payload = {
        "_portfolio_execution_path": "committee_endpoint",
        "calls": [],
        "votes": [
            {
                "seat_key": "macro",
                "agent_slug": "macro-analyst",
                "symbol": "SPY",
                "prob_up": 0.7,
                "expected_move_pct": 1.5,
                "confidence_score": 70,
                "source_clusters": [{"cluster": "market_regime", "weight": 0.8}],
            },
        ],
    }
    source_snapshot = _fresh_source_snapshot()
    source_snapshot["clusters"]["market_regime"]["latest_closes"]["XLK"]["date"] = "2026-03-23"
    fake_client = _FakeRoundtableClient(raw_payload)
    service = MarketPredictionCommitteeService(
        repository=repo,
        storage=_FakeStorage(),
        roundtable_client_factory=lambda **_: fake_client,
    )
    monkeypatch.setattr("app.services.market_prediction_committee_service.get_expected_data_date", lambda _now: date(2026, 4, 21))
    monkeypatch.setattr("app.services.market_prediction_committee_service.get_macro_calendar_cluster", lambda **kwargs: kwargs.get("existing") or {})
    monkeypatch.setattr(service, "_build_statistical_baseline_votes", lambda **_: [], raising=False)

    result = service.generate_snapshot(
        window_days=3,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        source_snapshot=source_snapshot,
    )

    fact_check = repo.runs[0].metadata["fact_check_report"]
    assert fact_check["status"] == "fail"
    assert "market_regime_stale" in [issue["code"] for issue in fact_check["issues"]]
    assert result.lead_call.prob_up == pytest.approx(0.5)
    assert result.lead_call.expected_move_pct == pytest.approx(0.0)
    assert result.lead_call.metadata["publication_state"] == "no_edge"
    assert "fact_check_failed" in result.lead_call.metadata["abstain_reason_codes"]
    assert result.committee_summary["fact_check_status"] == "fail"



def test_generate_snapshot_filters_zero_weight_supported_clusters_from_new_weighted_attribution(monkeypatch) -> None:
    repo = _FakeRepo()
    raw_payload = {
        "_portfolio_execution_path": "committee_endpoint",
        "calls": [],
        "votes": [
            {
                "seat_key": "macro",
                "agent_slug": "macro-analyst",
                "symbol": "SPY",
                "prob_up": 0.7,
                "expected_move_pct": 1.2,
                "confidence_score": 70,
                "source_clusters": [
                    {"cluster": " sentiment ", "weight": 0.9},
                    {"cluster": "macro_calendar", "weight": 0.6},
                    {"cluster": "market_regime", "weight": 0.4},
                ],
            },
            {
                "seat_key": "risk",
                "agent_slug": "risk-manager",
                "symbol": "SPY",
                "prob_up": 0.45,
                "expected_move_pct": -0.5,
                "confidence_score": 55,
                "source_clusters": [
                    {"cluster": "market_regime", "weight": 0.5},
                    {"cluster": "unsupported_cluster", "weight": 1.0},
                ],
            },
        ],
    }
    review = MarketPredictionSeatReview(
        id="seat-review:3:2026-04-21T22:15:00+00:00",
        generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        window_days=3,
        review_state="live",
        seat_scorecards=[
            {"seat_key": "cross_asset", "prior_weight": 1 / 3, "effective_weight": 0.2, "sample_size": 6, "direction_hit_rate": 0.5, "move_mae_pct": 1.0, "brier_score": 0.2, "skill_score": 0.6, "recommended_action": "downweight"},
            {"seat_key": "macro", "prior_weight": 1 / 3, "effective_weight": 0.5, "sample_size": 12, "direction_hit_rate": 0.7, "move_mae_pct": 0.6, "brier_score": 0.12, "skill_score": 0.82, "recommended_action": "upweight"},
            {"seat_key": "risk", "prior_weight": 1 / 3, "effective_weight": 0.3, "sample_size": 10, "direction_hit_rate": 0.4, "move_mae_pct": 2.1, "brier_score": 0.35, "skill_score": 0.41, "recommended_action": "hold"},
        ],
        review_summary={"generated_at": "2026-04-21T22:15:00+00:00", "review_state": "live", "drift_callouts": [], "top_upweighted": [], "top_downweighted": []},
        metadata={"weighting_half_life_days": 20, "trailing_window_trading_days": 60, "backfill_run_limit": 120, "supported_windows": [1, 3, 7, 14]},
    )
    cluster_review = MarketPredictionClusterReview(
        id="cluster-review:3:2026-04-21T22:15:00+00:00",
        generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        window_days=3,
        review_state="live",
        cluster_scorecards=[
            {"cluster": "market_regime", "prior_weight": 0.25, "effective_weight": 0.32, "sample_size": 24, "direction_hit_rate": 0.6, "move_mae_pct": 0.9, "brier_score": 0.2, "skill_score": 0.7, "freshness": "fresh", "recommended_action": "upweight"},
            {"cluster": "sentiment", "prior_weight": 0.25, "effective_weight": 0.0, "sample_size": 4, "direction_hit_rate": None, "move_mae_pct": None, "brier_score": None, "skill_score": None, "freshness": "missing", "recommended_action": "downweight"},
            {"cluster": "options_positioning", "prior_weight": 0.25, "effective_weight": 0.0, "sample_size": 0, "direction_hit_rate": None, "move_mae_pct": None, "brier_score": None, "skill_score": None, "freshness": "missing", "recommended_action": "downweight"},
            {"cluster": "macro_calendar", "prior_weight": 0.25, "effective_weight": 0.40, "sample_size": 24, "direction_hit_rate": 1.0, "move_mae_pct": 0.1, "brier_score": 0.01, "skill_score": 0.98, "freshness": "fresh", "recommended_action": "upweight"},
        ],
        review_summary={"generated_at": "2026-04-21T22:15:00+00:00", "review_state": "live", "drift_callouts": [], "top_upweighted": [], "top_downweighted": []},
        metadata={"weighting_half_life_days": 20, "trailing_window_trading_days": 60, "freshness_factors": {"fresh": 1.0, "stale": 0.5, "missing": 0.0, "unknown": 0.25}, "supported_windows": [1, 3, 7, 14]},
    )
    fake_client = _FakeRoundtableClient(raw_payload)
    service = MarketPredictionCommitteeService(repository=repo, roundtable_client_factory=lambda **_: fake_client)

    monkeypatch.setattr("app.services.market_prediction_committee_service.get_expected_data_date", lambda _now: date(2026, 4, 21))
    monkeypatch.setattr(
        service,
        "_build_source_snapshot",
        lambda _: _fresh_source_snapshot(
            clusters={
                "sentiment": {"freshness": "missing"},
                "options_positioning": {"freshness": "missing"},
            }
        ),
    )
    monkeypatch.setattr("app.services.market_prediction_committee_service.get_macro_calendar_cluster", lambda **_: {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 1, "next_event_date": "2026-04-22"})

    result = service.generate_snapshot(
        window_days=3,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        review=review,
        cluster_review=cluster_review,
    )

    assert result.calls[0].metadata["active_cluster_keys"] == ["macro_calendar", "market_regime"]
    assert [cluster.cluster for cluster in result.calls[0].top_source_clusters] == ["macro_calendar", "market_regime"]
    assert result.source_snapshot["clusters"]["sentiment"]["effective_weight"] is None
    assert result.source_snapshot["clusters"]["macro_calendar"]["effective_weight"] == pytest.approx(0.4)



def test_generate_snapshot_ranks_fallback_clusters_when_scored_cluster_weights_exist(monkeypatch) -> None:
    repo = _FakeRepo()
    raw_payload = {
        "_portfolio_execution_path": "committee_endpoint",
        "calls": [],
        "votes": [
            {
                "seat_key": "macro",
                "agent_slug": "macro-analyst",
                "symbol": "SPY",
                "prob_up": 0.7,
                "expected_move_pct": 1.2,
                "confidence_score": 70,
                "source_clusters": [
                    {
                        "cluster": "market_regime",
                        "weight": 0.9,
                        "freshness": "fresh",
                        "note": "Awaiting scored history.",
                    },
                    {
                        "cluster": "macro_calendar",
                        "weight": 0.6,
                        "freshness": "stale",
                        "note": "Awaiting scored history.",
                    },
                ],
            },
            {
                "seat_key": "risk",
                "agent_slug": "risk-manager",
                "symbol": "SPY",
                "prob_up": 0.45,
                "expected_move_pct": -0.5,
                "confidence_score": 55,
                "source_clusters": [
                    {
                        "cluster": "market_regime",
                        "weight": 0.5,
                        "freshness": "fresh",
                        "note": "Awaiting scored history.",
                    }
                ],
            },
        ],
    }
    review = MarketPredictionSeatReview(
        id="seat-review:3:2026-04-21T22:15:00+00:00",
        generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        window_days=3,
        review_state="live",
        seat_scorecards=[
            {"seat_key": "cross_asset", "prior_weight": 1 / 3, "effective_weight": 0.2, "sample_size": 6, "direction_hit_rate": 0.5, "move_mae_pct": 1.0, "brier_score": 0.2, "skill_score": 0.6, "recommended_action": "downweight"},
            {"seat_key": "macro", "prior_weight": 1 / 3, "effective_weight": 0.5, "sample_size": 12, "direction_hit_rate": 0.7, "move_mae_pct": 0.6, "brier_score": 0.12, "skill_score": 0.82, "recommended_action": "upweight"},
            {"seat_key": "risk", "prior_weight": 1 / 3, "effective_weight": 0.3, "sample_size": 10, "direction_hit_rate": 0.4, "move_mae_pct": 2.1, "brier_score": 0.35, "skill_score": 0.41, "recommended_action": "hold"},
        ],
        review_summary={"generated_at": "2026-04-21T22:15:00+00:00", "review_state": "live", "drift_callouts": [], "top_upweighted": [], "top_downweighted": []},
        metadata={"weighting_half_life_days": 20, "trailing_window_trading_days": 60, "backfill_run_limit": 120, "supported_windows": [1, 3, 7, 14]},
    )
    cluster_review = MarketPredictionClusterReview(
        id="cluster-review:3:2026-04-21T22:15:00+00:00",
        generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        window_days=3,
        review_state="live",
        cluster_scorecards=[
            {"cluster": "market_regime", "prior_weight": 0.25, "effective_weight": 0.6, "sample_size": 24, "direction_hit_rate": 0.6, "move_mae_pct": 0.9, "brier_score": 0.2, "skill_score": 0.7, "freshness": "fresh", "recommended_action": "upweight"},
            {"cluster": "sentiment", "prior_weight": 0.25, "effective_weight": 0.1, "sample_size": 4, "direction_hit_rate": None, "move_mae_pct": None, "brier_score": None, "skill_score": None, "freshness": "fresh", "recommended_action": "hold"},
            {"cluster": "options_positioning", "prior_weight": 0.25, "effective_weight": 0.1, "sample_size": 0, "direction_hit_rate": None, "move_mae_pct": None, "brier_score": None, "skill_score": None, "freshness": "fresh", "recommended_action": "hold"},
            {"cluster": "macro_calendar", "prior_weight": 0.25, "effective_weight": 0.2, "sample_size": 24, "direction_hit_rate": 1.0, "move_mae_pct": 0.1, "brier_score": 0.01, "skill_score": 0.98, "freshness": "stale", "recommended_action": "downweight"},
        ],
        review_summary={"generated_at": "2026-04-21T22:15:00+00:00", "review_state": "live", "drift_callouts": [], "top_upweighted": [], "top_downweighted": []},
        metadata={"weighting_half_life_days": 20, "trailing_window_trading_days": 60, "freshness_factors": {"fresh": 1.0, "stale": 0.5, "missing": 0.0, "unknown": 0.25}, "supported_windows": [1, 3, 7, 14]},
    )
    fake_client = _FakeRoundtableClient(raw_payload)
    service = MarketPredictionCommitteeService(repository=repo, roundtable_client_factory=lambda **_: fake_client)

    monkeypatch.setattr("app.services.market_prediction_committee_service.get_expected_data_date", lambda _now: date(2026, 4, 21))
    monkeypatch.setattr(
        service,
        "_build_source_snapshot",
        lambda _: _fresh_source_snapshot(
            clusters={
                "sentiment": {"freshness": "fresh"},
                "macro_calendar": {"freshness": "stale", "reason": "stale_table"},
            }
        ),
    )
    monkeypatch.setattr("app.services.market_prediction_committee_service.get_macro_calendar_cluster", lambda **_: {"freshness": "stale", "reason": "stale_table", "upcoming_event_count": 0, "next_event_date": None})

    result = service.generate_snapshot(
        window_days=3,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        review=review,
        cluster_review=cluster_review,
    )

    assert result.calls[0].metadata["active_cluster_keys"] == ["market_regime"]
    assert [cluster.cluster for cluster in result.calls[0].top_source_clusters] == ["market_regime"]
    assert [cluster.weight for cluster in result.calls[0].top_source_clusters] == [pytest.approx(0.6)]
    assert {cluster.note for cluster in result.calls[0].top_source_clusters} == {"Ranked by scored history."}



def test_generate_snapshot_uses_single_seat_verbatim_consensus(monkeypatch) -> None:
    repo = _FakeRepo()
    raw_payload = {
        "_portfolio_execution_path": "committee_endpoint",
        "calls": [],
        "votes": [
            {
                "seat_key": "macro",
                "agent_slug": "macro-analyst",
                "symbol": "SPY",
                "prob_up": 0.8,
                "expected_move_pct": 2.0,
                "confidence_score": 80,
                "source_clusters": [{"cluster": "macro_calendar", "weight": 0.6}],
            },
            {
                "seat_key": "new-seat",
                "agent_slug": "ignored-seat",
                "symbol": "SPY",
                "prob_up": 0.1,
                "expected_move_pct": -3.0,
                "confidence_score": 20,
                "source_clusters": [{"cluster": "market_regime", "weight": 0.4}],
            },
        ],
    }
    review = MarketPredictionSeatReview(
        id="seat-review:3:2026-04-21T22:15:00+00:00",
        generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        window_days=3,
        review_state="live",
        seat_scorecards=[
            {"seat_key": "cross_asset", "prior_weight": 1 / 3, "effective_weight": 0.2, "sample_size": 6, "direction_hit_rate": 0.5, "move_mae_pct": 1.0, "brier_score": 0.2, "skill_score": 0.6, "recommended_action": "downweight"},
            {"seat_key": "macro", "prior_weight": 1 / 3, "effective_weight": 0.5, "sample_size": 12, "direction_hit_rate": 0.7, "move_mae_pct": 0.6, "brier_score": 0.12, "skill_score": 0.82, "recommended_action": "upweight"},
            {"seat_key": "risk", "prior_weight": 1 / 3, "effective_weight": 0.3, "sample_size": 10, "direction_hit_rate": 0.4, "move_mae_pct": 2.1, "brier_score": 0.35, "skill_score": 0.41, "recommended_action": "hold"},
        ],
        review_summary={"generated_at": "2026-04-21T22:15:00+00:00", "review_state": "live", "drift_callouts": [], "top_upweighted": [], "top_downweighted": []},
        metadata={"weighting_half_life_days": 20, "trailing_window_trading_days": 60, "backfill_run_limit": 120, "supported_windows": [1, 3, 7, 14]},
    )
    fake_client = _FakeRoundtableClient(raw_payload)
    service = MarketPredictionCommitteeService(repository=repo, roundtable_client_factory=lambda **_: fake_client)

    monkeypatch.setattr("app.services.market_prediction_committee_service.get_expected_data_date", lambda _now: date(2026, 4, 21))
    monkeypatch.setattr(service, "_build_source_snapshot", lambda _: _fresh_source_snapshot())
    monkeypatch.setattr("app.services.market_prediction_committee_service.get_macro_calendar_cluster", lambda **_: {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 1, "next_event_date": "2026-04-22"})

    result = service.generate_snapshot(window_days=3, as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC), review=review)

    assert result.calls[0].prob_up == pytest.approx(0.71)
    assert result.calls[0].metadata["probability_calibration"]["raw_prob_up"] == pytest.approx(0.8)
    assert result.calls[0].expected_move_pct == pytest.approx(2.0)
    assert result.calls[0].confidence_band_low_pct == pytest.approx(2.0)
    assert result.calls[0].confidence_band_high_pct == pytest.approx(2.0)
    assert result.calls[0].committee_disagreement_score == pytest.approx(0.0)
    assert result.calls[0].metadata["aggregation_mode"] == "single_seat"
    assert result.calls[0].metadata["active_seat_keys"] == ["macro"]



def test_generate_snapshot_falls_back_neutral_when_all_votes_use_unknown_seats(monkeypatch) -> None:
    repo = _FakeRepo()
    raw_payload = {
        "_portfolio_execution_path": "committee_endpoint",
        "calls": [],
        "votes": [
            {
                "seat_key": "new-seat",
                "agent_slug": "ignored-seat",
                "symbol": "SPY",
                "prob_up": 0.1,
                "expected_move_pct": -3.0,
                "confidence_score": 20,
                "source_clusters": [{"cluster": "market_regime", "weight": 0.4}],
            }
        ],
    }
    review = MarketPredictionSeatReview(
        id="seat-review:3:2026-04-21T22:15:00+00:00",
        generated_at=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
        window_days=3,
        review_state="warmup",
        seat_scorecards=[
            {"seat_key": "cross_asset", "prior_weight": 1 / 3, "effective_weight": 1 / 3, "sample_size": 0, "direction_hit_rate": None, "move_mae_pct": None, "brier_score": None, "skill_score": None, "recommended_action": "hold"},
            {"seat_key": "macro", "prior_weight": 1 / 3, "effective_weight": 1 / 3, "sample_size": 0, "direction_hit_rate": None, "move_mae_pct": None, "brier_score": None, "skill_score": None, "recommended_action": "hold"},
            {"seat_key": "risk", "prior_weight": 1 / 3, "effective_weight": 1 / 3, "sample_size": 0, "direction_hit_rate": None, "move_mae_pct": None, "brier_score": None, "skill_score": None, "recommended_action": "hold"},
        ],
        review_summary={"generated_at": "2026-04-21T22:15:00+00:00", "review_state": "warmup", "drift_callouts": [], "top_upweighted": [], "top_downweighted": []},
        metadata={"weighting_half_life_days": 20, "trailing_window_trading_days": 60, "backfill_run_limit": 120, "supported_windows": [1, 3, 7, 14]},
    )
    fake_client = _FakeRoundtableClient(raw_payload)
    service = MarketPredictionCommitteeService(repository=repo, roundtable_client_factory=lambda **_: fake_client)

    monkeypatch.setattr("app.services.market_prediction_committee_service.get_expected_data_date", lambda _now: date(2026, 4, 21))
    monkeypatch.setattr(service, "_build_source_snapshot", lambda _: _fresh_source_snapshot())
    monkeypatch.setattr("app.services.market_prediction_committee_service.get_macro_calendar_cluster", lambda **_: {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 1, "next_event_date": "2026-04-22"})

    result = service.generate_snapshot(window_days=3, as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC), review=review)

    assert result.calls[0].prob_up == pytest.approx(0.5)
    assert result.calls[0].expected_move_pct == pytest.approx(0.0)
    assert result.calls[0].confidence_score == pytest.approx(0.0)
    assert result.calls[0].committee_disagreement_score == pytest.approx(0.0)
    assert result.calls[0].metadata["aggregation_mode"] == "neutral_fallback"
    assert result.calls[0].metadata["active_seat_keys"] == []


def test_generate_snapshot_uses_statistical_baseline_when_agent_votes_are_empty(monkeypatch) -> None:
    repo = _FakeRepo()
    raw_payload = {
        "_portfolio_execution_path": "committee_endpoint",
        "calls": [],
        "votes": [],
    }
    fake_client = _FakeRoundtableClient(raw_payload)
    service = MarketPredictionCommitteeService(repository=repo, roundtable_client_factory=lambda **_: fake_client)
    baseline_vote = CommitteeSeatVote(
        seat_key="baseline",
        agent_slug="statistical-baseline",
        model_id="statistical-baseline-v1",
        provider="portfolio-ai",
        symbol="SPY",
        window_days=3,
        direction_label="bullish",
        prob_up=0.6,
        expected_move_pct=1.0,
        confidence_score=55.0,
        rationale_summary="Deterministic baseline.",
        source_clusters=[{"cluster": "market_regime", "freshness": "fresh"}],
        metadata={"baseline_version": "statistical-baseline-v1"},
    )

    monkeypatch.setattr("app.services.market_prediction_committee_service.get_expected_data_date", lambda _now: date(2026, 4, 21))
    monkeypatch.setattr(
        service,
        "_build_source_snapshot",
        lambda _: _fresh_source_snapshot(),
    )
    monkeypatch.setattr(
        service,
        "_build_statistical_baseline_votes",
        lambda **_: [baseline_vote],
        raising=False,
    )
    monkeypatch.setattr("app.services.market_prediction_committee_service.get_macro_calendar_cluster", lambda **_: {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 1, "next_event_date": "2026-04-22"})

    result = service.generate_snapshot(window_days=3, as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC))

    assert repo.votes == [baseline_vote]
    assert result.calls[0].metadata["aggregation_mode"] == "single_seat"
    assert result.calls[0].metadata["active_seat_keys"] == ["baseline"]
    assert result.calls[0].prob_up == pytest.approx(0.57)
    assert result.calls[0].direction_label == "bullish"
    assert result.calls[0].metadata["probability_calibration"]["version"] == "sample-shrink-v1"
    assert result.calls[0].metadata["publication_state"] == "forecast"
    assert result.committee_summary["baseline_vote_count"] == 1
    assert result.committee_summary["publication_state"] == "forecast"
    assert result.committee_summary["executed_seat_keys"] == ["baseline"]
    assert len(repo.runs[0].metadata["prompt_hash"]) == 64
    assert len(repo.runs[0].metadata["published_calls_hash"]) == 64


def test_normalize_response_reconciles_stale_attribution_freshness(monkeypatch) -> None:
    repo = _FakeRepo()
    repo.snapshot = _response(
        lead_call=_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4, "freshness": "fresh"}]),
        calls=[_call(symbol="SPY", clusters=[{"cluster": "market_regime", "weight": 0.4, "freshness": "fresh"}])],
        source_snapshot={
            "clusters": {
                "market_regime": {
                    "latest_closes": _fresh_latest_closes(date(2026, 4, 20))
                },
                "macro_calendar": {"freshness": "fresh", "reason": "ok", "upcoming_event_count": 1, "next_event_date": "2026-04-22"},
            }
        },
    )
    service = MarketPredictionCommitteeService(repository=repo)
    monkeypatch.setattr("app.services.market_prediction_committee_service.get_expected_data_date", lambda _now: date(2026, 4, 21))
    monkeypatch.setattr("app.services.market_prediction_committee_service.get_macro_calendar_cluster", lambda **kwargs: kwargs.get("existing") or {})

    result = service.get_committee_snapshot(window_days=3)

    assert result is not None
    assert result.source_snapshot["clusters"]["market_regime"]["freshness"] == "stale"
    assert result.lead_call.top_source_clusters[0].freshness == "stale"



def test_generate_snapshot_persists_root_provenance_and_generation_time_fallbacks(monkeypatch) -> None:
    repo = _FakeRepo()
    raw_payload = {
        "_portfolio_execution_path": "committee_endpoint",
        "calls": [
            {
                "symbol": "SPY",
                "prob_up": 0.62,
                "expected_move_pct": 1.4,
                "confidence_score": 78,
                "top_source_clusters": [],
            }
        ],
        "votes": [
            {
                "seat_key": " Macro ",
                "agent_slug": "market-pulse-analyst",
                "model_id": "gpt-5.4",
                "provider": "codex",
                "symbol": "SPY",
                "prob_up": 0.64,
                "expected_move_pct": 1.6,
                "confidence_score": 81,
                "source_clusters": [],
            }
        ],
    }
    fake_client = _FakeRoundtableClient(raw_payload)
    service = MarketPredictionCommitteeService(
        repository=repo,
        roundtable_client_factory=lambda **_: fake_client,
    )

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        service,
        "_build_source_snapshot",
        lambda _: _fresh_source_snapshot(
            clusters={
                "sentiment": {"freshness": "fresh"},
                "macro_calendar": {
                    "freshness": "fresh",
                    "reason": "ok",
                    "upcoming_event_count": 2,
                    "next_event_date": "2026-04-22",
                },
            }
        ),
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: {
            "freshness": "fresh",
            "reason": "ok",
            "upcoming_event_count": 2,
            "next_event_date": "2026-04-22",
        },
    )

    result = service.generate_snapshot(
        window_days=3,
        as_of_ts=datetime(2026, 4, 21, 22, 15, tzinfo=UTC),
    )

    assert fake_client.closed is True
    assert fake_client.call_kwargs is not None
    assert "Use independent LLM seat roles exactly" in fake_client.call_kwargs["prompt"]
    assert '"seat_key": "cross_asset"' in fake_client.call_kwargs["prompt"]
    assert "Each seat must reason independently" in fake_client.call_kwargs["prompt"]
    assert repo.runs[0].metadata["committee_execution_path"] == "committee_endpoint"
    assert repo.runs[0].metadata["committee_roster_mode"] == "custom_roster"
    assert repo.runs[0].metadata["executed_seats"] == [
        {
            "seat_key": "macro",
            "agent_slug": "market-pulse-analyst",
            "model_id": "gpt-5.4",
            "provider": "codex",
        }
    ]
    assert len(repo.runs[0].metadata["committee_fingerprint"]) == 64
    assert repo.votes[0].source_clusters[0].cluster == "macro_calendar"
    assert repo.calls[0].top_source_clusters[0].cluster == "macro_calendar"
    assert result.committee_summary["committee_execution_path"] == "committee_endpoint"
    assert result.committee_summary["executed_seat_keys"] == ["macro"]
    assert result.committee_summary["truth_state"] == "pending_target"
    assert result.committee_summary["scorecard_status_note"]
    assert "_portfolio_execution_path" not in result.committee_summary


def test_macro_helper_failure_defaults_macro_contract_without_fetch_error(monkeypatch) -> None:
    repo = _FakeRepo()
    repo.snapshot = _response(
        lead_call=_call(clusters=[{"cluster": "market_regime", "weight": 0.4}]),
        calls=[_call(clusters=[{"cluster": "market_regime", "weight": 0.4}])],
        source_snapshot={"clusters": {"macro_calendar": {"legacy_flag": True}}},
    )
    service = MarketPredictionCommitteeService(repository=repo)

    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_expected_data_date",
        lambda _now: date(2026, 4, 21),
    )
    monkeypatch.setattr(
        "app.services.market_prediction_committee_service.get_macro_calendar_cluster",
        lambda **_: (_ for _ in ()).throw(RuntimeError("macro helper failed")),
    )

    result = service.get_committee_snapshot(window_days=3)

    assert result is not None
    assert result.committee_summary["truth_state"] == "pending_target"
    assert result.source_snapshot["clusters"]["macro_calendar"] == {
        "legacy_flag": True,
        "freshness": "unknown",
    }
