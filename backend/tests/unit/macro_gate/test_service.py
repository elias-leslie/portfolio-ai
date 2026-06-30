from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import cast

from app.macro_gate import service
from app.macro_gate.scoring import ComponentScores, CompositeResult, RawSignals, classify_zone
from app.portfolio.models import PriceData


def _degraded_result(score: float) -> CompositeResult:
    return CompositeResult(
        raw=RawSignals(None, None, None, None, None, None),
        scores=ComponentScores(None, None, None, None, None, None),
        deployment_score=score,
        zone=classify_zone(score),
        coverage=0.75,
        metadata={"degraded": True, "stale_components": ["vix"]},
    )


def test_infer_snapshot_date_uses_new_york_market_date(monkeypatch) -> None:
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz == service.NY_TZ
            return cls(2026, 6, 4, 20, 30, tzinfo=service.NY_TZ)

    monkeypatch.setattr(service, "datetime", FixedDatetime)

    assert service._infer_snapshot_date(cast(CompositeResult, object())) == date(2026, 6, 4)


def test_collect_crowding_reuses_fresh_cached_observation(monkeypatch) -> None:
    monkeypatch.setattr(
        service.repository,
        "get_latest_crowding",
        lambda: {"factor_crowding_corr": 0.24, "as_of": date.today().isoformat()},
    )

    def fail_compute():  # pragma: no cover - should not be called
        raise AssertionError("fresh cached crowding should be reused")

    monkeypatch.setattr(service.factor_crowding, "compute_crowding", fail_compute)

    crowding = service._collect_crowding()

    assert crowding is not None
    assert crowding.value == 0.24
    assert crowding.source == "cached_weekly"


def test_stale_component_keys_only_degrades_intraday_inputs() -> None:
    metadata = {
        "component_quality": {
            "vix": {"status": "stale"},  # intraday input carried forward -> degrades
            "credit": {"status": "stale"},  # daily T+1 lag is cadence-normal, not degrading
            "term": {"status": "fresh"},
            "breadth": {"status": "missing"},
        }
    }
    assert service._stale_component_keys(metadata) == frozenset({"vix"})


def test_clamp_holds_greener_degraded_reading_to_known_good(monkeypatch) -> None:
    monkeypatch.setattr(service.repository, "get_last_known_good_score", lambda _d: 45.0)

    clamped = service._clamp_degraded_to_known_good(_degraded_result(80.0), date(2026, 6, 4))

    assert clamped.deployment_score == 45.0
    assert clamped.zone == "REDUCED"
    assert clamped.metadata["clamped_to_known_good"] is True
    assert clamped.metadata["raw_deployment_score"] == 80.0


def test_clamp_keeps_more_cautious_degraded_reading(monkeypatch) -> None:
    monkeypatch.setattr(service.repository, "get_last_known_good_score", lambda _d: 45.0)

    clamped = service._clamp_degraded_to_known_good(_degraded_result(30.0), date(2026, 6, 4))

    assert clamped.deployment_score == 30.0
    assert "clamped_to_known_good" not in clamped.metadata
    assert clamped.metadata["known_good_score"] == 45.0


def test_clamp_is_noop_without_known_good_reference(monkeypatch) -> None:
    monkeypatch.setattr(service.repository, "get_last_known_good_score", lambda _d: None)

    clamped = service._clamp_degraded_to_known_good(_degraded_result(80.0), date(2026, 6, 4))

    assert clamped.deployment_score == 80.0
    assert clamped.metadata["known_good_score"] is None


def test_collect_signals_uses_canonical_current_vix_quote(monkeypatch) -> None:
    quote_time = datetime(2026, 6, 4, 13, 25, tzinfo=UTC)

    def compute_breadth(*, as_of: date | None = None) -> SimpleNamespace:
        del as_of
        return SimpleNamespace(pct_above_200dma=54.8, as_of=date(2026, 6, 3))

    def collect_crowding(snapshot_date: date | None = None) -> service.CrowdingSignal:
        del snapshot_date
        return service.CrowdingSignal(
            value=-0.85,
            as_of=date(2026, 5, 26),
            source="cached_weekly",
        )

    def fake_storage() -> object:
        return object()

    monkeypatch.setattr(
        service.fear_greed_components,
        "fetch_latest",
        lambda: SimpleNamespace(
            as_of=date(2026, 6, 3),
            vix_close=16.06,
            vix_as_of=date(2026, 6, 3),
            vix_stale=False,
            hy_spread=2.71,
            hy_spread_as_of=date(2026, 6, 3),
            hy_spread_stale=False,
            put_call_ratio=1.34,
        ),
    )
    monkeypatch.setattr(
        service.term_structure,
        "fetch_latest",
        lambda: SimpleNamespace(spread_bps=41.0, as_of=date(2026, 6, 2)),
    )
    monkeypatch.setattr(
        service.spx_breadth_200d,
        "compute_breadth",
        compute_breadth,
    )
    monkeypatch.setattr(service, "_collect_crowding", collect_crowding)
    monkeypatch.setattr(service, "get_storage", fake_storage)

    class FakePriceDataFetcher:
        def __init__(self, _storage: object) -> None:
            pass

        def fetch_price_data(
            self,
            symbols: list[str],
            *,
            force_refresh: bool = False,
            max_age_minutes: int | None = None,
        ) -> dict[str, PriceData]:
            assert symbols == ["^VIX"]
            assert force_refresh is True
            assert max_age_minutes == 0
            return {
                "^VIX": PriceData(
                    symbol="^VIX",
                    price=16.39,
                    cached_at=quote_time,
                    source="yfinance",
                )
            }

    monkeypatch.setattr(service, "PriceDataFetcher", FakePriceDataFetcher)

    collected = service.collect_signals(
        force_quote_refresh=True,
        current_quote_max_age_minutes=0,
    )

    assert collected.raw.vix_close == 16.39
    quality = collected.metadata["component_quality"]["vix"]
    assert quality["source"] == "price_cache.^VIX via yfinance"
    assert quality["cadence"] == "intraday_current"
    assert quality["as_of"] == quote_time.isoformat()


def test_run_loads_database_credentials_before_collecting(monkeypatch) -> None:
    calls: list[str] = []

    def load_credentials() -> None:
        calls.append("credentials")

    def collect_signals(**_kwargs) -> service.CollectedSignals:
        calls.append("collect")
        return service.CollectedSignals(
            raw=RawSignals(16.0, 40.0, 55.0, 2.7, 1.2, -0.2),
            metadata={"component_quality": {}},
        )

    monkeypatch.setattr(service, "load_credentials_from_database", load_credentials)
    monkeypatch.setattr(service, "collect_signals", collect_signals)

    output = service.run(snapshot_date=date(2026, 6, 30), persist=False)

    assert output is not None
    assert calls == ["credentials", "collect"]
