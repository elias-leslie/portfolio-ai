from __future__ import annotations

from datetime import date

from app.macro_gate import service


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
