from __future__ import annotations

import json

from app.tasks._ml_training_helpers import (
    _load_training_data,
    _merge_gemini_labels,
    _query_new_articles,
)


class _FakeConnection:
    def __init__(self, rows: list[tuple[str | None, str | None, str | None]]) -> None:
        self.rows = rows
        self.executed: list[str] = []

    def execute(self, sql: str) -> None:
        self.executed.append(sql)

    def fetchall(self) -> list[tuple[str | None, str | None, str | None]]:
        return self.rows


def test_load_training_data_normalizes_ticker_and_returns_hashes(tmp_path) -> None:
    training_data_path = tmp_path / "training.json"
    training_data_path.write_text(
        json.dumps(
            [
                {"ticker": "AAPL", "headline": "Apple launch event", "summary": "Summary"},
                {"symbol": "MSFT", "headline": "Microsoft earnings", "summary": "Summary"},
            ]
        )
    )

    existing_data, labeled_hashes = _load_training_data(training_data_path)

    assert existing_data[0]["symbol"] == "AAPL"
    assert existing_data[1]["symbol"] == "MSFT"
    assert "AAPL_Apple launch event" in labeled_hashes
    assert "MSFT_Microsoft earnings" in labeled_hashes


def test_query_new_articles_filters_labeled_articles_and_applies_limit() -> None:
    conn = _FakeConnection(
        rows=[
            ("AAPL", "Apple launch event", "Existing"),
            ("MSFT", "Microsoft earnings", "Fresh"),
            ("NVDA", "Nvidia guides higher", "Fresh"),
        ]
    )

    articles = _query_new_articles(conn, {"AAPL_Apple launch event"}, limit=1)

    assert len(articles) == 1
    assert articles[0]["symbol"] == "MSFT"
    assert "FROM news_cache" in conn.executed[0]


def test_merge_gemini_labels_matches_articles_by_symbol_and_headline_prefix() -> None:
    article_headline = "Apple launch event confirms device revenue guidance"

    merged = _merge_gemini_labels(
        gemini_labels=[
            {
                "symbol": "AAPL",
                "headline": f"{article_headline} after investor call",
                "is_useful": True,
                "reasons": ["specific_data"],
                "confidence": "high",
            }
        ],
        new_articles=[
            {
                "symbol": "AAPL",
                "headline": article_headline,
                "summary": "Summary",
            }
        ],
    )

    assert merged == [
        {
            "symbol": "AAPL",
            "headline": article_headline,
            "summary": "Summary",
            "is_useful": True,
            "gemini_reasons": ["specific_data"],
            "gemini_confidence": "high",
        }
    ]
