from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

from app.tasks.market_data import fear_greed_data


class _Result:
    def __init__(self, *, one=None, rows=None):
        self._one = one
        self._rows = rows or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._rows


class _Connection:
    def execute(self, query: str, _params=None):
        if "FROM fear_greed_inputs" in query:
            return _Result(one=(16.9, 2.8))
        if "FROM day_bars" in query:
            return _Result(rows=[(dt.date(2026, 5, 22), 16.9)])
        return _Result()


class _ConnectionContext:
    def __enter__(self):
        return _Connection()

    def __exit__(self, *_args):
        return False


class _Storage:
    def connection(self):
        return _ConnectionContext()


class _PriceDataFetcher:
    def __init__(self, _storage):
        pass

    def fetch_price_data(self, _symbols):
        return {
            "^VIX": SimpleNamespace(
                price=16.7,
                cached_at=dt.datetime(2026, 5, 22, 22, 7, tzinfo=dt.UTC),
            )
        }


class _FredSource:
    def fetch_series(self, _indicator, _start_date, _end_date):
        return [(dt.date(2026, 5, 22), 2.78)]


def test_fetch_market_indicators_overlays_fresher_current_vix(monkeypatch) -> None:
    monkeypatch.setattr(fear_greed_data, "PriceDataFetcher", _PriceDataFetcher)
    monkeypatch.setattr(fear_greed_data, "FREDSource", _FredSource)

    vix_dict, hy_dict, vix_estimate, hy_fallback = fear_greed_data.fetch_market_indicators(
        _Storage(), dt.date(2026, 5, 22), dt.date(2026, 5, 22)
    )

    assert vix_dict[dt.date(2026, 5, 22)] == 16.7
    assert hy_dict[dt.date(2026, 5, 22)] == 2.78
    assert vix_estimate == 16.9
    assert hy_fallback == 2.8
