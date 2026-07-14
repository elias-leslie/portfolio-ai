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


def test_build_symbol_intelligence_preserves_sections_after_source_failure(
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.api.symbols.service._storage", _stub_storage)
    monkeypatch.setattr(
        "app.api.symbols.service._watchlist_service",
        _stub_watchlist_service,
    )
    monkeypatch.setattr(
        "app.api.symbols.service.fetch_all_data",
        lambda *_args, **_kwargs: {
            "quote": {
                "price": 122.04,
                "freshness_status": "unknown",
                "freshness_label": "Quote time unavailable",
            },
            "watchlist": {
                "symbol": "VTI",
                "overall_score": 78,
                "signal_type": "BUY",
                "signal_strength": 7,
            },
            "portfolio": {},
            "strategies": None,
            "news": {"article_count": 2},
            "market": {"vix": 18.2},
            "section_issues": [
                {
                    "section": "portfolio",
                    "message": "Portfolio position context is temporarily unavailable.",
                }
            ],
        },
    )

    response = build_symbol_intelligence("vti", include_decision=False)

    assert response.quote is not None
    assert response.quote.price == 122.04
    assert response.scores is not None
    assert response.scores.overall == 78
    assert response.news is not None
    assert response.news.article_count_24h == 2
    assert response.market is not None
    assert response.market.vix == 18.2
    assert response.portfolio is None
    assert response.recommendation is None
    assert [issue.section for issue in response.section_issues] == [
        "portfolio",
        "recommendation",
    ]
    payload = response.model_dump(mode="json")
    assert payload["error"] is None
    assert payload["section_issues"] == [
        {
            "section": "portfolio",
            "message": "Portfolio position context is temporarily unavailable.",
        },
        {
            "section": "recommendation",
            "message": (
                "The live recommendation is unavailable because required signal or "
                "portfolio inputs did not load."
            ),
        },
    ]


def test_build_symbol_intelligence_isolates_section_builder_failure(monkeypatch) -> None:
    monkeypatch.setattr("app.api.symbols.service._storage", _stub_storage)
    monkeypatch.setattr(
        "app.api.symbols.service._watchlist_service",
        _stub_watchlist_service,
    )
    monkeypatch.setattr(
        "app.api.symbols.service.fetch_all_data",
        lambda *_args, **_kwargs: {
            "quote": None,
            "watchlist": None,
            "portfolio": {"position": None, "summary": None},
            "strategies": None,
            "news": {},
            "market": {"vix": 18.2},
            "section_issues": [],
        },
    )
    monkeypatch.setattr(
        "app.api.symbols.service.build_market_section",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("malformed market payload")
        ),
    )

    response = build_symbol_intelligence("vti", include_decision=False)

    assert response.portfolio is not None
    assert response.market is None
    assert response.recommendation is not None
    assert [issue.section for issue in response.section_issues] == ["market"]


def test_build_symbol_intelligence_marks_response_fatal_only_when_nothing_is_usable(
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.api.symbols.service._storage", _stub_storage)
    monkeypatch.setattr(
        "app.api.symbols.service._watchlist_service",
        _stub_watchlist_service,
    )
    monkeypatch.setattr(
        "app.api.symbols.service.fetch_all_data",
        lambda *_args, **_kwargs: {
            "quote": {},
            "watchlist": None,
            "portfolio": {},
            "strategies": None,
            "news": {},
            "market": {},
            "section_issues": [
                {
                    "section": "watchlist",
                    "message": "Scores and signal evidence are temporarily unavailable.",
                },
                {
                    "section": "portfolio",
                    "message": "Portfolio position context is temporarily unavailable.",
                },
            ],
        },
    )

    response = build_symbol_intelligence("vti", include_decision=False)

    assert response.error == "Symbol intelligence is temporarily unavailable."
    assert response.quote is None
    assert response.portfolio is None
    assert response.recommendation is None
