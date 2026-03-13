from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.tasks._ml_training_helpers import (
    _article_hash,
    _headlines_match,
    _load_training_data,
    _merge_gemini_labels,
    _normalize_training_article,
    _parse_gemini_output,
    _query_new_articles,
    _row_to_article,
    _write_articles_to_tempfile,
)


class _FakeConnection:
    def __init__(self, rows: list[tuple[str | None, str | None, str | None]]) -> None:
        self.rows = rows
        self.executed: list[str] = []
        self._rowcount = 0

    def execute(self, sql: str, parameters: Any = None) -> _FakeConnection:
        self.executed.append(sql)
        return self

    def fetchall(self) -> list[tuple[str | None, str | None, str | None]]:
        return self.rows

    def fetchone(self) -> tuple[str | None, str | None, str | None] | None:
        return self.rows[0] if self.rows else None

    def commit(self) -> None:
        pass

    @property
    def rowcount(self) -> int:
        return self._rowcount


# --- _load_training_data ---


def test_load_training_data_normalizes_ticker_and_returns_hashes(tmp_path: Path) -> None:
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


def test_load_training_data_missing_file_returns_empty(tmp_path: Path) -> None:
    missing_path = tmp_path / "nonexistent.json"
    existing_data, labeled_hashes = _load_training_data(missing_path)
    assert existing_data == []
    assert labeled_hashes == set()


# --- _normalize_training_article ---


def test_normalize_training_article_prefers_symbol_over_ticker() -> None:
    article = {"symbol": "AAPL", "ticker": "WRONG", "headline": "h"}
    assert _normalize_training_article(article)["symbol"] == "AAPL"


def test_normalize_training_article_falls_back_to_ticker() -> None:
    article = {"ticker": "GOOG", "headline": "h"}
    assert _normalize_training_article(article)["symbol"] == "GOOG"


def test_normalize_training_article_missing_both_returns_empty() -> None:
    article = {"headline": "h"}
    assert _normalize_training_article(article)["symbol"] == ""


# --- _article_hash ---


def test_article_hash_truncates_headline() -> None:
    long_headline = "A" * 100
    h = _article_hash("AAPL", long_headline)
    assert h == f"AAPL_{'A' * 50}"


def test_article_hash_short_headline() -> None:
    assert _article_hash("MSFT", "Short") == "MSFT_Short"


# --- _row_to_article ---


def test_row_to_article_converts_tuple() -> None:
    row = ("AAPL", "Apple headline", "Apple summary")
    result = _row_to_article(row)
    assert result == {"symbol": "AAPL", "headline": "Apple headline", "summary": "Apple summary"}


def test_row_to_article_handles_none_values() -> None:
    row = (None, None, None)
    result = _row_to_article(row)
    assert result == {"symbol": "", "headline": "", "summary": ""}


# --- _query_new_articles ---


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


def test_query_new_articles_returns_all_when_under_limit() -> None:
    conn = _FakeConnection(
        rows=[("MSFT", "Microsoft earnings", "Fresh")]
    )
    articles = _query_new_articles(conn, set(), limit=100)
    assert len(articles) == 1


# --- _headlines_match ---


def test_headlines_match_same_prefix() -> None:
    gemini = {"symbol": "AAPL", "headline": "Apple reports record revenue this quarter"}
    article = {"symbol": "AAPL", "headline": "Apple reports record revenue this quarter with strong guidance"}
    assert _headlines_match(gemini, article) is True


def test_headlines_match_case_insensitive() -> None:
    gemini = {"symbol": "AAPL", "headline": "APPLE Reports Record Revenue For Fourth Quarter Earnings"}
    article = {"symbol": "AAPL", "headline": "apple reports record revenue for fourth quarter earnings call"}
    assert _headlines_match(gemini, article) is True


def test_headlines_match_different_symbol() -> None:
    gemini = {"symbol": "AAPL", "headline": "Same headline here"}
    article = {"symbol": "MSFT", "headline": "Same headline here"}
    assert _headlines_match(gemini, article) is False


def test_headlines_match_different_headline() -> None:
    gemini = {"symbol": "AAPL", "headline": "Completely different headline text"}
    article = {"symbol": "AAPL", "headline": "Some other headline entirely for Apple"}
    assert _headlines_match(gemini, article) is False


# --- _parse_gemini_output ---


def test_parse_gemini_output_extracts_json_array() -> None:
    stdout = 'Some preamble text [{"symbol": "AAPL", "is_useful": true}] trailing text'
    result = _parse_gemini_output(stdout, "")
    assert result == [{"symbol": "AAPL", "is_useful": True}]


def test_parse_gemini_output_raises_on_no_json() -> None:
    with pytest.raises(ValueError, match="Could not parse Gemini JSON output"):
        _parse_gemini_output("no json here at all", "")


def test_parse_gemini_output_handles_nested_brackets() -> None:
    stdout = '[{"reasons": ["a", "b"]}]'
    result = _parse_gemini_output(stdout, "")
    assert result == [{"reasons": ["a", "b"]}]


# --- _merge_gemini_labels ---


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


def test_merge_gemini_labels_skips_unmatched() -> None:
    merged = _merge_gemini_labels(
        gemini_labels=[
            {
                "symbol": "AAPL",
                "headline": "No match headline",
                "is_useful": True,
                "reasons": [],
                "confidence": "low",
            }
        ],
        new_articles=[
            {"symbol": "MSFT", "headline": "Different stock entirely", "summary": "s"},
        ],
    )
    assert merged == []


# --- _write_articles_to_tempfile ---


def test_write_articles_to_tempfile_creates_file() -> None:
    articles = [
        {"symbol": "AAPL", "headline": "Test headline", "summary": "Test summary"},
    ]
    path = _write_articles_to_tempfile(articles)
    try:
        content = Path(path).read_text(encoding="utf-8")
        assert "AAPL|Test headline|Test summary" in content
    finally:
        Path(path).unlink(missing_ok=True)


def test_write_articles_to_tempfile_multiple_articles() -> None:
    articles = [
        {"symbol": "AAPL", "headline": "H1", "summary": "S1"},
        {"symbol": "MSFT", "headline": "H2", "summary": "S2"},
    ]
    path = _write_articles_to_tempfile(articles)
    try:
        lines = Path(path).read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert lines[0] == "AAPL|H1|S1"
        assert lines[1] == "MSFT|H2|S2"
    finally:
        Path(path).unlink(missing_ok=True)
