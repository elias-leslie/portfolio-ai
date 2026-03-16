from __future__ import annotations

import time
from contextlib import nullcontext
from unittest.mock import MagicMock

from app.tasks._watchlist_helpers import execute_refresh
from app.watchlist.refresh_data_fetchers import fetch_auxiliary_data


def _null_task_logger(*_args: object, **_kwargs: object):
    return nullcontext()


def test_execute_refresh_uses_lightweight_background_mode(monkeypatch) -> None:
    mock_storage = MagicMock()
    mock_refresh = MagicMock(return_value={"processed": 2, "failed": 0, "skipped": 0})

    monkeypatch.setattr("app.tasks._watchlist_helpers.get_storage", lambda: mock_storage)
    monkeypatch.setattr("app.tasks._watchlist_helpers.is_market_hours", lambda: True)
    monkeypatch.setattr("app.tasks._watchlist_helpers.task_logger", _null_task_logger)
    monkeypatch.setattr("app.tasks._watchlist_helpers.refresh_watchlist_scores_service", mock_refresh)
    monkeypatch.setattr(
        "app.tasks._watchlist_helpers.trigger_strategy_generation_for_top_symbols",
        lambda: (_ for _ in ()).throw(AssertionError("strategy trigger should not run")),
    )

    result = execute_refresh(
        account_id="default",
        task_id="task-123",
        refresh_interval_minutes=15,
        start_time=time.time(),
    )

    assert result["processed"] == 2
    mock_refresh.assert_called_once_with(
        mock_storage,
        account_id="default",
        include_news=False,
    )


def test_fetch_auxiliary_data_skips_news_when_disabled() -> None:
    storage = MagicMock()
    news_service = MagicMock()

    volume_df = MagicMock()
    volume_df.height = 0

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = None
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.__exit__.return_value = False

    storage.query.return_value = volume_df
    storage.connection.return_value = mock_conn

    current_volume, avg_volume_20d, sma_5_prev, news_sentiment_value, news_bundle = (
        fetch_auxiliary_data(
            storage=storage,
            news_service=news_service,
            symbol="AAPL",
            max_news_articles=10,
            news_bundle=None,
            include_news=False,
        )
    )

    assert current_volume is None
    assert avg_volume_20d is None
    assert sma_5_prev is None
    assert news_sentiment_value is None
    assert news_bundle is None
    news_service.get_news_intelligence.assert_not_called()
