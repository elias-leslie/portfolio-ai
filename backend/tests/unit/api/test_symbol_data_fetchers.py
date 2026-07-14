"""Unit tests for symbol intelligence data fetchers."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock

from app.api.symbols.data_fetchers import (
    fetch_all_data,
    get_quote_data,
    get_strategies_data,
    get_watchlist_data,
)
from app.portfolio.models import PriceData


def test_get_watchlist_data_uses_watchlist_items_without_decision_enrichment(mocker) -> None:
    """Symbol intelligence should not request recursive watchlist decisions."""
    watchlist_service = Mock()
    watchlist_service.get_items_with_scores.return_value = [{"symbol": "NVDA"}]
    build_mock = mocker.patch(
        "app.api.symbols.data_fetchers._build_watchlist_result",
        return_value={"symbol": "NVDA", "signal_type": "BUY"},
    )

    result = get_watchlist_data("nvda", watchlist_service)

    watchlist_service.get_items_with_scores.assert_called_once_with(include_decision=False)
    build_mock.assert_called_once_with({"symbol": "NVDA"})
    assert result == {"symbol": "NVDA", "signal_type": "BUY"}


def test_get_strategies_data_returns_retired_payload_without_query() -> None:
    storage = Mock()

    result = get_strategies_data("AAPL", storage)

    assert result == {"strategies": [], "active_count": 0, "best": None}
    storage.connection.assert_not_called()


def test_fetch_all_data_keeps_valid_sections_when_portfolio_fails(monkeypatch) -> None:
    """A failed source should be explicit without discarding other source data."""
    monkeypatch.setattr(
        "app.api.symbols.data_fetchers.get_quote_data",
        lambda *_args, **_kwargs: {"price": 122.04},
    )
    monkeypatch.setattr(
        "app.api.symbols.data_fetchers.get_watchlist_data",
        lambda *_args, **_kwargs: {"symbol": "VTI", "signal_type": "BUY"},
    )
    monkeypatch.setattr(
        "app.api.symbols.data_fetchers.get_portfolio_data",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("portfolio store unavailable")
        ),
    )
    monkeypatch.setattr(
        "app.api.symbols.data_fetchers.get_strategies_data",
        lambda *_args, **_kwargs: {"strategies": []},
    )
    monkeypatch.setattr(
        "app.api.symbols.data_fetchers.get_news_data",
        lambda *_args, **_kwargs: {"article_count": 2},
    )
    monkeypatch.setattr(
        "app.api.symbols.data_fetchers.get_market_data",
        lambda *_args, **_kwargs: {"vix": 18.2},
    )

    result = fetch_all_data("VTI", Mock(), Mock(), True, True)

    assert result["quote"] == {"price": 122.04}
    assert result["watchlist"] == {"symbol": "VTI", "signal_type": "BUY"}
    assert result["portfolio"] == {}
    assert result["news"] == {"article_count": 2}
    assert result["market"] == {"vix": 18.2}
    assert result["section_issues"] == [
        {
            "section": "portfolio",
            "message": "Portfolio position context is temporarily unavailable.",
        }
    ]


def test_get_quote_data_reads_canonical_price_with_short_ttl(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeFetcher:
        def __init__(self, storage: object) -> None:
            self.storage = storage

        def fetch_price_data(
            self,
            symbols: list[str],
            *,
            force_refresh: bool = False,
            max_age_minutes: int | None = None,
        ) -> dict[str, PriceData]:
            calls.append(
                {
                    "symbols": symbols,
                    "force_refresh": force_refresh,
                    "max_age_minutes": max_age_minutes,
                }
            )
            return {
                "VGT": PriceData(
                    symbol="VGT",
                    price=122.04,
                    source="yfinance",
                    cached_at=datetime(2026, 6, 4, 13, 15, tzinfo=UTC),
                )
            }

    monkeypatch.setattr("app.api.symbols.data_fetchers.PriceDataFetcher", FakeFetcher)

    result = get_quote_data("vgt", object(), force_refresh=True)

    assert result["price"] == 122.04
    assert result["source"] == "yfinance"
    assert result["session"] == "pre_market"
    assert calls == [
        {
            "symbols": ["VGT"],
            "force_refresh": True,
            "max_age_minutes": 1,
        }
    ]


def test_get_quote_data_falls_back_to_latest_cache_when_refresh_fails(monkeypatch) -> None:
    class FakeFetcher:
        def __init__(self, storage: object) -> None:
            self.storage = storage

        def fetch_price_data(
            self,
            _symbols: list[str],
            *,
            force_refresh: bool = False,
            max_age_minutes: int | None = None,
        ) -> dict[str, PriceData]:
            return {
                "VGT": PriceData(
                    symbol="VGT",
                    price=0.0,
                    source="multi_source",
                    error="vendor unavailable",
                )
            }

        def fetch_cached_price_data(
            self,
            _symbols: list[str],
            *,
            max_age_minutes: int | None = None,
        ) -> dict[str, PriceData]:
            return {
                "VGT": PriceData(
                    symbol="VGT",
                    price=121.88,
                    source="yfinance",
                    cached_at=datetime(2026, 6, 4, 12, 40, tzinfo=UTC),
                )
            }

    monkeypatch.setattr("app.api.symbols.data_fetchers.PriceDataFetcher", FakeFetcher)

    result = get_quote_data("VGT", object(), force_refresh=True)

    assert result["price"] == 121.88
    assert result["error"] == "vendor unavailable"
