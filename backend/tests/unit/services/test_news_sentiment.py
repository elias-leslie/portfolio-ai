"""Unit tests for optional news sentiment dependencies."""

from __future__ import annotations

from app.services.news_sentiment import _load_finbert_dependencies


def test_load_finbert_dependencies_returns_none_when_optional_packages_missing(mocker) -> None:
    """FinBERT helpers should degrade cleanly when heavy packages are absent."""

    def raise_import_error(name: str):  # type: ignore[no-untyped-def]
        raise ImportError(f"missing {name}")

    mocker.patch("app.services.news_sentiment.import_module", side_effect=raise_import_error)

    torch, auto_tokenizer, auto_model = _load_finbert_dependencies()

    assert torch is None
    assert auto_tokenizer is None
    assert auto_model is None
