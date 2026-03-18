"""Unit tests for watchlist discovery and trimming tasks.

Tests cover:
- discover_watchlist_candidates_task with mocked storage
- trim_underperforming_watchlist_task with mocked storage
- Helper functions: get_top_gainers, get_volume_spikes, get_news_mentions
- calculate_discovery_score edge cases
- Edge cases: empty results, watchlist full, auto_trim disabled
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.rules.models import WatchlistManagementRules
from app.tasks.watchlist_discovery import (
    discover_watchlist_candidates_task,
    trim_underperforming_watchlist_task,
)
from app.tasks.watchlist_discovery.helpers import (
    add_symbol_to_watchlist,
    calculate_discovery_score,
    get_existing_watchlist_symbols,
    get_news_mentions,
    get_top_gainers,
    get_volume_spikes,
    get_watchlist_size,
)
from app.tasks.watchlist_discovery.trimming import (
    get_trim_candidates,
    remove_symbol_from_watchlist,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_storage() -> MagicMock:
    """Create mock PortfolioStorage for testing."""
    storage = MagicMock()
    return storage


@pytest.fixture
def mock_rules() -> WatchlistManagementRules:
    """Create default watchlist management rules."""
    return WatchlistManagementRules(
        max_watchlist_size=50,
        max_daily_additions=5,
        max_daily_removals=3,
        discovery_score_threshold=6.0,
        gainers_threshold_pct=5.0,
        volume_spike_ratio=2.0,
        news_mention_threshold=3,
        auto_trim_enabled=True,
        min_days_watched=7,
        min_score_threshold=4.0,
        exclude_portfolio_holdings=True,
    )


# =============================================================================
# Test Helper Functions
# =============================================================================


class TestGetTopGainers:
    """Test get_top_gainers helper function."""

    def test_returns_gainers_above_threshold(self, mock_storage: MagicMock) -> None:
        """Test returns symbols with gains above threshold."""
        # Mock polars DataFrame response
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = [
            {"symbol": "AAPL", "close": 150.0, "prev_close": 140.0, "change_pct": 7.14},
            {"symbol": "TSLA", "close": 200.0, "prev_close": 180.0, "change_pct": 11.11},
        ]
        mock_storage.query.return_value = mock_df

        result = get_top_gainers(mock_storage, threshold_pct=5.0, limit=20)

        assert len(result) == 2
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["change_pct"] == 7.14
        assert result[1]["symbol"] == "TSLA"
        assert result[1]["change_pct"] == 11.11

        # Verify SQL query called with correct params
        mock_storage.query.assert_called_once()
        args = mock_storage.query.call_args[0]
        assert args[1] == [5.0, 20]  # threshold_pct, limit

    def test_handles_empty_results(self, mock_storage: MagicMock) -> None:
        """Test handles no gainers found."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = []
        mock_storage.query.return_value = mock_df

        result = get_top_gainers(mock_storage)

        assert result == []

    def test_handles_null_values(self, mock_storage: MagicMock) -> None:
        """Test handles NULL values in database response."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = [
            {"symbol": "AAPL", "close": None, "prev_close": 140.0, "change_pct": None},
        ]
        mock_storage.query.return_value = mock_df

        result = get_top_gainers(mock_storage)

        assert len(result) == 1
        assert result[0]["close"] == 0.0
        assert result[0]["change_pct"] == 0.0


class TestGetVolumeSpikes:
    """Test get_volume_spikes helper function."""

    def test_returns_volume_spikes_above_ratio(self, mock_storage: MagicMock) -> None:
        """Test returns symbols with volume spikes above ratio."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = [
            {
                "symbol": "AAPL",
                "latest_volume": 100000000,
                "avg_volume": 40000000.0,
                "volume_ratio": 2.5,
            },
            {
                "symbol": "NVDA",
                "latest_volume": 150000000,
                "avg_volume": 50000000.0,
                "volume_ratio": 3.0,
            },
        ]
        mock_storage.query.return_value = mock_df

        result = get_volume_spikes(mock_storage, spike_ratio=2.0, limit=20)

        assert len(result) == 2
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["volume"] == 100000000
        assert result[0]["volume_ratio"] == 2.5
        assert result[1]["symbol"] == "NVDA"
        assert result[1]["volume_ratio"] == 3.0

    def test_handles_empty_results(self, mock_storage: MagicMock) -> None:
        """Test handles no volume spikes found."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = []
        mock_storage.query.return_value = mock_df

        result = get_volume_spikes(mock_storage)

        assert result == []

    def test_converts_volume_to_int(self, mock_storage: MagicMock) -> None:
        """Test converts volume to integer properly."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = [
            {
                "symbol": "AAPL",
                "latest_volume": 50000000.5,
                "avg_volume": 25000000.0,
                "volume_ratio": 2.0,
            },
        ]
        mock_storage.query.return_value = mock_df

        result = get_volume_spikes(mock_storage)

        assert result[0]["volume"] == 50000000  # Converted to int


class TestGetNewsMentions:
    """Test get_news_mentions helper function."""

    def test_returns_symbols_with_mentions_above_threshold(self, mock_storage: MagicMock) -> None:
        """Test returns symbols with news mentions above threshold."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = [
            {"symbol": "AAPL", "article_count": 5, "avg_sentiment": 0.3},
            {"symbol": "NVDA", "article_count": 8, "avg_sentiment": 0.5},
        ]
        mock_storage.query.return_value = mock_df

        result = get_news_mentions(mock_storage, min_mentions=3, hours=24, limit=20)

        assert len(result) == 2
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["article_count"] == 5
        assert result[0]["avg_sentiment"] == 0.3
        assert result[1]["symbol"] == "NVDA"
        assert result[1]["article_count"] == 8

    def test_handles_empty_results(self, mock_storage: MagicMock) -> None:
        """Test handles no news mentions found."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = []
        mock_storage.query.return_value = mock_df

        result = get_news_mentions(mock_storage)

        assert result == []

    def test_handles_null_sentiment(self, mock_storage: MagicMock) -> None:
        """Test handles NULL sentiment values."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = [
            {"symbol": "AAPL", "article_count": 5, "avg_sentiment": None},
        ]
        mock_storage.query.return_value = mock_df

        result = get_news_mentions(mock_storage)

        assert len(result) == 1
        assert result[0]["avg_sentiment"] == 0.0


class TestCalculateDiscoveryScore:
    """Test calculate_discovery_score helper function."""

    def test_perfect_score_all_signals_max(self) -> None:
        """Test perfect score with max values in all signals."""
        gainers_data = [{"symbol": "AAPL", "change_pct": 25.0}]
        volume_data = [{"symbol": "AAPL", "volume_ratio": 6.0}]
        news_data = [{"symbol": "AAPL", "article_count": 12}]

        score = calculate_discovery_score("AAPL", gainers_data, volume_data, news_data)

        # Max score: 4 (gainers) + 4 (volume) + 4 (news) = 12
        assert score == 12.0

    def test_mid_range_scores(self) -> None:
        """Test mid-range values produce expected scores."""
        gainers_data = [{"symbol": "AAPL", "change_pct": 12.0}]  # 2 points
        volume_data = [{"symbol": "AAPL", "volume_ratio": 3.5}]  # 2 points
        news_data = [{"symbol": "AAPL", "article_count": 6}]  # 2 points

        score = calculate_discovery_score("AAPL", gainers_data, volume_data, news_data)

        assert score == 6.0

    def test_single_signal_only(self) -> None:
        """Test scoring with only one signal present."""
        gainers_data = [{"symbol": "AAPL", "change_pct": 20.0}]
        volume_data: list[dict[str, str | float]] = []
        news_data: list[dict[str, str | float | int]] = []

        score = calculate_discovery_score("AAPL", gainers_data, volume_data, news_data)

        assert score == 4.0  # Only gainers score

    def test_symbol_not_in_data(self) -> None:
        """Test returns zero for symbol not in any data source."""
        gainers_data = [{"symbol": "TSLA", "change_pct": 20.0}]
        volume_data = [{"symbol": "NVDA", "volume_ratio": 5.0}]
        news_data = [{"symbol": "AMD", "article_count": 10}]

        score = calculate_discovery_score("AAPL", gainers_data, volume_data, news_data)

        assert score == 0.0

    def test_gainers_thresholds(self) -> None:
        """Test gainers scoring thresholds."""
        test_cases = [
            (4.0, 0.0),  # Below threshold
            (5.0, 1.0),  # 5-10%
            (10.0, 2.0),  # 10-15%
            (15.0, 3.0),  # 15-20%
            (20.0, 4.0),  # 20%+
        ]

        for change_pct, expected_score in test_cases:
            gainers_data = [{"symbol": "AAPL", "change_pct": change_pct}]
            score = calculate_discovery_score("AAPL", gainers_data, [], [])
            assert score == expected_score, f"Failed for change_pct={change_pct}"

    def test_volume_thresholds(self) -> None:
        """Test volume scoring thresholds."""
        test_cases = [
            (1.5, 0.0),  # Below threshold
            (2.0, 1.0),  # 2-3x
            (3.0, 2.0),  # 3-4x
            (4.0, 3.0),  # 4-5x
            (5.0, 4.0),  # 5x+
        ]

        for ratio, expected_score in test_cases:
            volume_data = [{"symbol": "AAPL", "volume_ratio": ratio}]
            score = calculate_discovery_score("AAPL", [], volume_data, [])
            assert score == expected_score, f"Failed for volume_ratio={ratio}"

    def test_news_thresholds(self) -> None:
        """Test news scoring thresholds."""
        test_cases = [
            (2, 0.0),  # Below threshold
            (3, 1.0),  # 3-5 articles
            (5, 2.0),  # 5-7 articles
            (7, 3.0),  # 7-10 articles
            (10, 4.0),  # 10+ articles
        ]

        for count, expected_score in test_cases:
            news_data = [{"symbol": "AAPL", "article_count": count}]
            score = calculate_discovery_score("AAPL", [], [], news_data)
            assert score == expected_score, f"Failed for article_count={count}"


class TestGetExistingWatchlistSymbols:
    """Test get_existing_watchlist_symbols helper function."""

    def test_returns_symbol_set(self, mock_storage: MagicMock) -> None:
        """Test returns set of existing watchlist symbols."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = [
            {"symbol": "AAPL"},
            {"symbol": "TSLA"},
            {"symbol": "NVDA"},
        ]
        mock_storage.query.return_value = mock_df

        result = get_existing_watchlist_symbols(mock_storage)

        assert result == {"AAPL", "TSLA", "NVDA"}
        assert isinstance(result, set)

    def test_returns_empty_set_when_no_items(self, mock_storage: MagicMock) -> None:
        """Test returns empty set when watchlist is empty."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = []
        mock_storage.query.return_value = mock_df

        result = get_existing_watchlist_symbols(mock_storage)

        assert result == set()


class TestGetWatchlistSize:
    """Test get_watchlist_size helper function."""

    def test_returns_count(self, mock_storage: MagicMock) -> None:
        """Test returns watchlist item count."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = [{"cnt": 25}]
        mock_storage.query.return_value = mock_df

        result = get_watchlist_size(mock_storage)

        assert result == 25

    def test_returns_zero_when_empty(self, mock_storage: MagicMock) -> None:
        """Test returns zero when watchlist is empty."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = [{"cnt": 0}]
        mock_storage.query.return_value = mock_df

        result = get_watchlist_size(mock_storage)

        assert result == 0

    def test_handles_null_count(self, mock_storage: MagicMock) -> None:
        """Test handles NULL count (edge case)."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = [{"cnt": None}]
        mock_storage.query.return_value = mock_df

        result = get_watchlist_size(mock_storage)

        assert result == 0

    def test_handles_empty_result_set(self, mock_storage: MagicMock) -> None:
        """Test handles empty result set."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = []
        mock_storage.query.return_value = mock_df

        result = get_watchlist_size(mock_storage)

        assert result == 0


class TestAddSymbolToWatchlist:
    """Test add_symbol_to_watchlist helper function."""

    def test_successful_addition(self, mock_storage: MagicMock) -> None:
        """Test successful symbol addition to watchlist."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("test-item-id",)
        mock_conn = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        result = add_symbol_to_watchlist(mock_storage, "AAPL", 8.0, "discovery")

        assert result is not None
        # Verify symbol inserted via conn.execute (ensure_symbol_exists helper)
        conn_calls = mock_conn.execute.call_args_list
        assert any("INSERT INTO symbols" in str(c) for c in conn_calls)
        # Verify watchlist item inserted via cursor
        cursor_calls = mock_cursor.execute.call_args_list
        assert len(cursor_calls) == 1
        assert "INSERT INTO watchlist_items" in cursor_calls[0][0][0]
        mock_conn.commit.assert_called_once()

    def test_duplicate_symbol_returns_none(self, mock_storage: MagicMock) -> None:
        """Test adding duplicate symbol returns None (ON CONFLICT DO NOTHING)."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # No row returned due to conflict
        mock_conn = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        result = add_symbol_to_watchlist(mock_storage, "AAPL", 8.0)

        assert result is None

    def test_uppercase_conversion(self, mock_storage: MagicMock) -> None:
        """Test symbol is converted to uppercase."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("test-item-id",)
        mock_conn = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        add_symbol_to_watchlist(mock_storage, "aapl", 8.0)

        # Check that symbol was uppercased in ensure_symbol_exists call (conn.execute)
        conn_calls = mock_conn.execute.call_args_list
        symbol_call = next(c for c in conn_calls if "INSERT INTO symbols" in str(c))
        assert symbol_call[0][1][0] == "AAPL"
        # Check that symbol was uppercased in watchlist insert (cursor.execute)
        cursor_calls = mock_cursor.execute.call_args_list
        watchlist_call = cursor_calls[0][0][1]
        assert watchlist_call[1] == "AAPL"

    def test_metadata_includes_discovery_info(self, mock_storage: MagicMock) -> None:
        """Test metadata includes discovery score and date."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("test-item-id",)
        mock_conn = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        add_symbol_to_watchlist(mock_storage, "AAPL", 8.5)

        # Check metadata in watchlist_items insert (now the first cursor call)
        calls = mock_cursor.execute.call_args_list
        metadata_json = calls[0][0][1][4]  # 5th parameter (metadata)
        metadata = json.loads(metadata_json)
        assert metadata["discovery_score"] == 8.5
        assert metadata["auto_added"] is True
        assert "discovery_date" in metadata

    def test_exception_returns_none(self, mock_storage: MagicMock) -> None:
        """Test database exception returns None."""
        mock_storage.connection.side_effect = Exception("Database error")

        result = add_symbol_to_watchlist(mock_storage, "AAPL", 8.0)

        assert result is None


class TestGetTrimCandidates:
    """Test get_trim_candidates helper function."""

    def test_returns_underperforming_symbols(self, mock_storage: MagicMock) -> None:
        """Test returns symbols eligible for trimming."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = [
            {"id": "item-1", "symbol": "AAPL", "days_watched": 10, "avg_score": 2.5},
            {"id": "item-2", "symbol": "TSLA", "days_watched": 14, "avg_score": 3.0},
        ]
        mock_storage.query.return_value = mock_df

        result = get_trim_candidates(
            mock_storage,
            min_days_watched=7,
            min_score_threshold=4.0,
            exclude_portfolio=True,
        )

        assert len(result) == 2
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["avg_score"] == 2.5
        assert result[1]["symbol"] == "TSLA"
        assert result[1]["avg_score"] == 3.0

    def test_excludes_portfolio_holdings_when_enabled(self, mock_storage: MagicMock) -> None:
        """Test excludes portfolio holdings when flag is True."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = []
        mock_storage.query.return_value = mock_df

        get_trim_candidates(mock_storage, exclude_portfolio=True)

        # Check SQL includes exclusion clause
        sql = mock_storage.query.call_args[0][0]
        assert "NOT IN" in sql
        assert "portfolio_positions" in sql

    def test_includes_portfolio_holdings_when_disabled(self, mock_storage: MagicMock) -> None:
        """Test includes portfolio holdings when flag is False."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = []
        mock_storage.query.return_value = mock_df

        get_trim_candidates(mock_storage, exclude_portfolio=False)

        # Check SQL does NOT include exclusion clause
        sql = mock_storage.query.call_args[0][0]
        # With exclude_portfolio=False, the exclude_clause is empty
        assert "NOT IN" not in sql or "portfolio_positions" not in sql

    def test_handles_empty_results(self, mock_storage: MagicMock) -> None:
        """Test handles no trim candidates found."""
        mock_df = MagicMock()
        mock_df.iter_rows.return_value = []
        mock_storage.query.return_value = mock_df

        result = get_trim_candidates(mock_storage)

        assert result == []


class TestRemoveSymbolFromWatchlist:
    """Test remove_symbol_from_watchlist helper function."""

    def test_successful_removal(self, mock_storage: MagicMock) -> None:
        """Test successful symbol removal from watchlist."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("item-id",)
        mock_conn = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        result = remove_symbol_from_watchlist(
            mock_storage,
            "item-id",
            "AAPL",
            "avg_score=2.5 < 4.0",
        )

        assert result is True
        # Verify snapshots deleted first (FK constraint)
        calls = mock_cursor.execute.call_args_list
        assert len(calls) == 2
        assert "DELETE FROM watchlist_snapshots_core" in calls[0][0][0]
        assert "DELETE FROM watchlist_items" in calls[1][0][0]
        mock_conn.commit.assert_called_once()

    def test_nonexistent_item_returns_false(self, mock_storage: MagicMock) -> None:
        """Test removing nonexistent item returns False."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # No row deleted
        mock_conn = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        result = remove_symbol_from_watchlist(mock_storage, "nonexistent", "AAPL", "test")

        assert result is False

    def test_exception_returns_false(self, mock_storage: MagicMock) -> None:
        """Test database exception returns False."""
        mock_storage.connection.side_effect = Exception("Database error")

        result = remove_symbol_from_watchlist(mock_storage, "item-id", "AAPL", "test")

        assert result is False


# =============================================================================
# Test Main Tasks
# =============================================================================


class TestDiscoverWatchlistCandidatesTask:
    """Test discover_watchlist_candidates_task main task."""

    @patch("app.tasks.watchlist_discovery.discovery.get_rules")
    @patch("app.tasks.watchlist_discovery.discovery.PortfolioStorage")
    def test_successful_discovery_and_addition(
        self,
        mock_storage_class: MagicMock,
        mock_get_rules: MagicMock,
        mock_rules: WatchlistManagementRules,
    ) -> None:
        """Test successful candidate discovery and addition."""
        mock_get_rules.return_value.watchlist_management = mock_rules
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock get_watchlist_size
        size_df = MagicMock()
        size_df.iter_rows.return_value = [{"cnt": 10}]

        # Mock get_existing_watchlist_symbols
        existing_df = MagicMock()
        existing_df.iter_rows.return_value = [{"symbol": "MSFT"}]

        # Mock discovery data - AAPL with high scores to meet 6.0 threshold
        gainers_df = MagicMock()
        gainers_df.iter_rows.return_value = [
            {"symbol": "AAPL", "close": 150.0, "prev_close": 140.0, "change_pct": 20.0},  # 4 points
            {
                "symbol": "NVDA",
                "close": 500.0,
                "prev_close": 450.0,
                "change_pct": 11.11,
            },  # 2 points
        ]

        volume_df = MagicMock()
        volume_df.iter_rows.return_value = [
            {
                "symbol": "AAPL",
                "latest_volume": 100000000,
                "avg_volume": 40000000.0,
                "volume_ratio": 5.0,
            },  # 4 points
        ]

        news_df = MagicMock()
        news_df.iter_rows.return_value = [
            {
                "symbol": "AAPL",
                "article_count": 5,
                "avg_sentiment": 0.3,
            },  # 2 points = total 10 points
        ]

        mock_storage.query.side_effect = [size_df, gainers_df, volume_df, news_df, existing_df]

        # Mock add_symbol_to_watchlist
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("item-id",)
        mock_conn = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        result = discover_watchlist_candidates_task()

        assert result["status"] == "success"
        assert result["candidates_found"] == 2  # AAPL, NVDA (excluding MSFT)
        assert len(result["added"]) >= 1  # At least AAPL should qualify with score 10

    @patch("app.tasks.watchlist_discovery.discovery.get_rules")
    @patch("app.tasks.watchlist_discovery.discovery.PortfolioStorage")
    def test_skips_when_watchlist_full(
        self,
        mock_storage_class: MagicMock,
        mock_get_rules: MagicMock,
        mock_rules: WatchlistManagementRules,
    ) -> None:
        """Test skips discovery when watchlist is at max size."""
        mock_get_rules.return_value.watchlist_management = mock_rules
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock watchlist size at max
        size_df = MagicMock()
        size_df.iter_rows.return_value = [{"cnt": 50}]  # max_watchlist_size
        mock_storage.query.return_value = size_df

        result = discover_watchlist_candidates_task()

        assert result["status"] == "skipped"
        assert result["reason"] == "watchlist_full"
        assert result["current_size"] == 50

    @patch("app.tasks.watchlist_discovery.discovery.get_rules")
    @patch("app.tasks.watchlist_discovery.discovery.PortfolioStorage")
    def test_respects_max_daily_additions_limit(
        self,
        mock_storage_class: MagicMock,
        mock_get_rules: MagicMock,
        mock_rules: WatchlistManagementRules,
    ) -> None:
        """Test respects max_daily_additions limit."""
        mock_get_rules.return_value.watchlist_management = mock_rules
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock small watchlist
        size_df = MagicMock()
        size_df.iter_rows.return_value = [{"cnt": 5}]

        # Mock no existing symbols
        existing_df = MagicMock()
        existing_df.iter_rows.return_value = []

        # Mock many candidates (10 symbols, all with high scores)
        gainers_df = MagicMock()
        gainers_df.iter_rows.return_value = [
            {"symbol": f"SYM{i}", "close": 150.0, "prev_close": 140.0, "change_pct": 20.0}
            for i in range(10)
        ]

        volume_df = MagicMock()
        volume_df.iter_rows.return_value = [
            {
                "symbol": f"SYM{i}",
                "latest_volume": 100000000,
                "avg_volume": 40000000.0,
                "volume_ratio": 5.0,
            }
            for i in range(10)
        ]

        news_df = MagicMock()
        news_df.iter_rows.return_value = [
            {"symbol": f"SYM{i}", "article_count": 10, "avg_sentiment": 0.5} for i in range(10)
        ]

        mock_storage.query.side_effect = [size_df, gainers_df, volume_df, news_df, existing_df]

        # Mock successful additions
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("item-id",)
        mock_conn = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        result = discover_watchlist_candidates_task()

        assert result["status"] == "success"
        # Should add at most max_daily_additions (5)
        assert len(result["added"]) <= mock_rules.max_daily_additions

    @patch("app.tasks.watchlist_discovery.discovery.get_rules")
    @patch("app.tasks.watchlist_discovery.discovery.PortfolioStorage")
    def test_respects_watchlist_size_limit(
        self,
        mock_storage_class: MagicMock,
        mock_get_rules: MagicMock,
        mock_rules: WatchlistManagementRules,
    ) -> None:
        """Test respects max_watchlist_size even if daily limit is higher."""
        mock_get_rules.return_value.watchlist_management = mock_rules
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock watchlist near max (48/50)
        size_df = MagicMock()
        size_df.iter_rows.return_value = [{"cnt": 48}]

        existing_df = MagicMock()
        existing_df.iter_rows.return_value = []

        # Mock 5 qualified candidates
        gainers_df = MagicMock()
        gainers_df.iter_rows.return_value = [
            {"symbol": f"SYM{i}", "close": 150.0, "prev_close": 140.0, "change_pct": 20.0}
            for i in range(5)
        ]

        volume_df = MagicMock()
        volume_df.iter_rows.return_value = []

        news_df = MagicMock()
        news_df.iter_rows.return_value = []

        mock_storage.query.side_effect = [size_df, gainers_df, volume_df, news_df, existing_df]

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("item-id",)
        mock_conn = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        result = discover_watchlist_candidates_task()

        # Should only add 2 (48 + 2 = 50, at max)
        assert len(result["added"]) <= 2

    @patch("app.tasks.watchlist_discovery.discovery.get_rules")
    @patch("app.tasks.watchlist_discovery.discovery.PortfolioStorage")
    def test_filters_below_score_threshold(
        self,
        mock_storage_class: MagicMock,
        mock_get_rules: MagicMock,
        mock_rules: WatchlistManagementRules,
    ) -> None:
        """Test filters candidates below discovery_score_threshold."""
        mock_get_rules.return_value.watchlist_management = mock_rules
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        size_df = MagicMock()
        size_df.iter_rows.return_value = [{"cnt": 10}]

        existing_df = MagicMock()
        existing_df.iter_rows.return_value = []

        # Mock low-scoring candidate (5% gain only = 1 point, below 6.0 threshold)
        gainers_df = MagicMock()
        gainers_df.iter_rows.return_value = [
            {"symbol": "LOWSCORE", "close": 105.0, "prev_close": 100.0, "change_pct": 5.0},
        ]

        volume_df = MagicMock()
        volume_df.iter_rows.return_value = []

        news_df = MagicMock()
        news_df.iter_rows.return_value = []

        mock_storage.query.side_effect = [size_df, gainers_df, volume_df, news_df, existing_df]

        result = discover_watchlist_candidates_task()

        assert result["status"] == "success"
        assert result["qualified"] == 0  # Score < threshold
        assert len(result["added"]) == 0

    @patch("app.tasks.watchlist_discovery.discovery.get_rules")
    @patch("app.tasks.watchlist_discovery.discovery.PortfolioStorage")
    def test_handles_empty_discovery_data(
        self,
        mock_storage_class: MagicMock,
        mock_get_rules: MagicMock,
        mock_rules: WatchlistManagementRules,
    ) -> None:
        """Test handles empty results from all discovery sources."""
        mock_get_rules.return_value.watchlist_management = mock_rules
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        size_df = MagicMock()
        size_df.iter_rows.return_value = [{"cnt": 10}]

        existing_df = MagicMock()
        existing_df.iter_rows.return_value = []

        empty_df = MagicMock()
        empty_df.iter_rows.return_value = []

        mock_storage.query.side_effect = [size_df, empty_df, empty_df, empty_df, existing_df]

        result = discover_watchlist_candidates_task()

        assert result["status"] == "success"
        assert result["candidates_found"] == 0
        assert result["qualified"] == 0
        assert len(result["added"]) == 0

    @patch("app.tasks.watchlist_discovery.discovery.get_rules")
    @patch("app.tasks.watchlist_discovery.discovery.PortfolioStorage")
    def test_handles_exception(
        self,
        mock_storage_class: MagicMock,
        mock_get_rules: MagicMock,
        mock_rules: WatchlistManagementRules,
    ) -> None:
        """Test handles exceptions gracefully."""
        mock_get_rules.return_value.watchlist_management = mock_rules

        # Mock storage initialization to succeed, but query to fail
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage
        mock_storage.query.side_effect = Exception("Database connection failed")

        result = discover_watchlist_candidates_task()

        assert result["status"] == "error"
        assert "Database connection failed" in result["error"]


class TestTrimUnderperformingWatchlistTask:
    """Test trim_underperforming_watchlist_task main task."""

    @patch("app.tasks.watchlist_discovery.trimming.get_rules")
    @patch("app.tasks.watchlist_discovery.trimming.PortfolioStorage")
    def test_successful_trimming(
        self,
        mock_storage_class: MagicMock,
        mock_get_rules: MagicMock,
        mock_rules: WatchlistManagementRules,
    ) -> None:
        """Test successful trimming of underperforming symbols."""
        mock_get_rules.return_value.watchlist_management = mock_rules
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock trim candidates
        candidates_df = MagicMock()
        candidates_df.iter_rows.return_value = [
            {"id": "item-1", "symbol": "AAPL", "days_watched": 10, "avg_score": 2.5},
            {"id": "item-2", "symbol": "TSLA", "days_watched": 14, "avg_score": 3.0},
        ]
        mock_storage.query.return_value = candidates_df

        # Mock successful removal
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("item-id",)
        mock_conn = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        result = trim_underperforming_watchlist_task()

        assert result["status"] == "success"
        assert result["candidates_found"] == 2
        assert len(result["removed"]) == 2

    @patch("app.tasks.watchlist_discovery.trimming.get_automation_preferences")
    @patch("app.tasks.watchlist_discovery.trimming.get_rules")
    def test_skips_when_auto_trim_disabled(
        self,
        mock_get_rules: MagicMock,
        mock_get_automation_preferences: MagicMock,
        mock_rules: WatchlistManagementRules,
    ) -> None:
        """Test skips trimming when auto_trim_enabled is False."""
        # Override auto_trim_enabled
        mock_rules = WatchlistManagementRules(
            max_watchlist_size=50,
            max_daily_additions=5,
            max_daily_removals=3,
            discovery_score_threshold=6.0,
            gainers_threshold_pct=5.0,
            volume_spike_ratio=2.0,
            news_mention_threshold=3,
            auto_trim_enabled=False,  # Disabled
            min_days_watched=7,
            min_score_threshold=4.0,
            exclude_portfolio_holdings=True,
        )
        mock_get_rules.return_value.watchlist_management = mock_rules
        mock_get_automation_preferences.return_value = {
            "auto_trim_enabled": {"enabled": False, "source": "preferences"}
        }

        result = trim_underperforming_watchlist_task()

        assert result["status"] == "skipped"
        assert result["reason"] == "auto_trim_disabled"

    @patch("app.tasks.watchlist_discovery.trimming.get_rules")
    @patch("app.tasks.watchlist_discovery.trimming.PortfolioStorage")
    def test_respects_max_daily_removals_limit(
        self,
        mock_storage_class: MagicMock,
        mock_get_rules: MagicMock,
        mock_rules: WatchlistManagementRules,
    ) -> None:
        """Test respects max_daily_removals limit."""
        mock_get_rules.return_value.watchlist_management = mock_rules
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock many trim candidates (5 symbols)
        candidates_df = MagicMock()
        candidates_df.iter_rows.return_value = [
            {"id": f"item-{i}", "symbol": f"SYM{i}", "days_watched": 10, "avg_score": 2.0}
            for i in range(5)
        ]
        mock_storage.query.return_value = candidates_df

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("item-id",)
        mock_conn = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        result = trim_underperforming_watchlist_task()

        assert result["status"] == "success"
        # Should remove at most max_daily_removals (3)
        assert len(result["removed"]) <= mock_rules.max_daily_removals

    @patch("app.tasks.watchlist_discovery.trimming.get_rules")
    @patch("app.tasks.watchlist_discovery.trimming.PortfolioStorage")
    def test_handles_empty_trim_candidates(
        self,
        mock_storage_class: MagicMock,
        mock_get_rules: MagicMock,
        mock_rules: WatchlistManagementRules,
    ) -> None:
        """Test handles no trim candidates found."""
        mock_get_rules.return_value.watchlist_management = mock_rules
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock empty results
        empty_df = MagicMock()
        empty_df.iter_rows.return_value = []
        mock_storage.query.return_value = empty_df

        result = trim_underperforming_watchlist_task()

        assert result["status"] == "success"
        assert result["candidates_found"] == 0
        assert len(result["removed"]) == 0

    @patch("app.tasks.watchlist_discovery.trimming.get_rules")
    @patch("app.tasks.watchlist_discovery.trimming.PortfolioStorage")
    def test_handles_exception(
        self,
        mock_storage_class: MagicMock,
        mock_get_rules: MagicMock,
        mock_rules: WatchlistManagementRules,
    ) -> None:
        """Test handles exceptions gracefully."""
        mock_get_rules.return_value.watchlist_management = mock_rules

        # Mock storage initialization to succeed, but query to fail
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage
        mock_storage.query.side_effect = Exception("Database connection failed")

        result = trim_underperforming_watchlist_task()

        assert result["status"] == "error"
        assert "Database connection failed" in result["error"]

    @patch("app.tasks.watchlist_discovery.trimming.get_rules")
    @patch("app.tasks.watchlist_discovery.trimming.PortfolioStorage")
    def test_removal_failure_does_not_crash_task(
        self,
        mock_storage_class: MagicMock,
        mock_get_rules: MagicMock,
        mock_rules: WatchlistManagementRules,
    ) -> None:
        """Test task continues if individual removal fails."""
        mock_get_rules.return_value.watchlist_management = mock_rules
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        candidates_df = MagicMock()
        candidates_df.iter_rows.return_value = [
            {"id": "item-1", "symbol": "AAPL", "days_watched": 10, "avg_score": 2.5},
        ]
        mock_storage.query.return_value = candidates_df

        # Mock removal failure (returns None)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # Simulate deletion failure
        mock_conn = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        result = trim_underperforming_watchlist_task()

        # Task should complete successfully even if removal fails
        assert result["status"] == "success"
        assert len(result["removed"]) == 0
