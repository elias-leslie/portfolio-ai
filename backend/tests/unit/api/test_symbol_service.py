"""Unit tests for shared symbol intelligence assembly."""

from __future__ import annotations

from app.api.symbols.service import build_symbol_intelligence


def _stub_storage() -> object:
    return object()


def _stub_watchlist_service() -> object:
    return object()


def _stub_fetch_all_data(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {
        "watchlist": None,
        "portfolio": {"position": None, "summary": None},
        "strategies": None,
        "news": {},
        "market": {},
    }


def _stub_recommendation(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {
        "action": "hold",
        "reasoning": ["No change"],
        "if_not_held": None,
    }


def test_build_symbol_intelligence_skips_jenny_context_when_decision_disabled(
    monkeypatch,
) -> None:
    """Thesis fetches should not load Jenny decision context."""

    monkeypatch.setattr(
        "app.api.symbols.service._storage",
        _stub_storage,
    )
    monkeypatch.setattr(
        "app.api.symbols.service._watchlist_service",
        _stub_watchlist_service,
    )
    monkeypatch.setattr(
        "app.api.symbols.service.fetch_all_data",
        _stub_fetch_all_data,
    )
    monkeypatch.setattr(
        "app.api.symbols.service.generate_recommendation",
        _stub_recommendation,
    )
    monkeypatch.setattr(
        "app.api.symbols.service._jenny_service",
        lambda: (_ for _ in ()).throw(AssertionError("Jenny context should be skipped")),
    )

    response = build_symbol_intelligence("nvda", include_decision=False)

    assert response.symbol == "NVDA"
    assert response.decision is None
    assert response.recommendation is not None
