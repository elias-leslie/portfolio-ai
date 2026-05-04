"""Unit tests for fundamental ingestion task setup."""

from __future__ import annotations

from app.tasks.ingestion import fundamental_ingestion


class _FakeStorage:
    def query(self, _sql: str, _params=None):
        raise AssertionError("ingest_fundamental_data should use watchlist_items cache")


class _FakeYFinanceSource:
    pass


def _empty_symbols(*_args, **_kwargs) -> list[str]:
    return []


def _fake_storage() -> _FakeStorage:
    return _FakeStorage()


def test_ingest_fundamental_data_uses_watchlist_items_cache(monkeypatch) -> None:
    monkeypatch.setattr(fundamental_ingestion, "PortfolioStorage", _fake_storage)
    monkeypatch.setattr(fundamental_ingestion, "YFinanceSource", _FakeYFinanceSource)
    monkeypatch.setattr(fundamental_ingestion, "get_watchlist_symbols_cached", _empty_symbols)

    result = fundamental_ingestion.ingest_fundamental_data()

    assert result == {"status": "skipped", "reason": "no_symbols"}
