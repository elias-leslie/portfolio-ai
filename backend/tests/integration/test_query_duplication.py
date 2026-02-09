"""Integration tests for database query and API call deduplication.

These tests validate hypotheses about duplicate queries and redundant API calls
across scheduled tasks and service layers. Each test measures actual behavior before
implementing fixes.

Test Strategy:
1. Measure baseline (before fixes)
2. Validate each hypothesis with measurements
3. Only implement fixes if hypothesis proven true
4. Re-measure to verify improvements
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from app.services import NewsBundle, NewsSummary
from app.storage import get_storage


class QueryCounter:
    """Helper to track and analyze database queries by patching execute method.

    Captures all SQL queries executed during a test, allowing analysis of
    duplicate queries and query patterns.
    """

    def __init__(self) -> None:
        """Initialize query counter with empty query list."""
        self.queries: list[dict[str, Any]] = []
        self._original_execute: Any = None
        self._patched = False

    def _capture_execute(self, original_func: Any) -> Any:
        """Create wrapper that captures queries.

        Args:
            original_func: Original execute method

        Returns:
            Wrapped function that captures queries
        """

        def wrapper(conn_wrapper: Any, query: str, parameters: list[Any] | None = None) -> Any:
            # Normalize query for comparison
            normalized_query = " ".join(query.split())

            # Capture query
            self.queries.append(
                {
                    "sql": normalized_query,
                    "params": parameters or [],
                    "timestamp": datetime.now(UTC),
                }
            )

            # Call original (with self)
            return original_func(conn_wrapper, query, parameters)

        return wrapper

    def start_listening(self) -> None:
        """Patch connection execute method to capture queries."""
        if not self._patched:
            from app.storage.connection import PostgreSQLConnectionWrapper

            # Store original and patch
            self._original_execute = PostgreSQLConnectionWrapper.execute
            PostgreSQLConnectionWrapper.execute = self._capture_execute(self._original_execute)
            self._patched = True

    def stop_listening(self) -> None:
        """Restore original execute method."""
        if self._patched and self._original_execute:
            from app.storage.connection import PostgreSQLConnectionWrapper

            PostgreSQLConnectionWrapper.execute = self._original_execute
            self._patched = False

    def get_queries_to_table(self, table_name: str) -> list[dict[str, Any]]:
        """Get all queries that reference a specific table.

        Args:
            table_name: Name of table to filter by (e.g., 'user_preferences')

        Returns:
            List of query dictionaries that reference the table
        """
        return [q for q in self.queries if table_name.lower() in q["sql"].lower()]

    def count_duplicate_queries(self) -> tuple[int, list[tuple[str, int]]]:
        """Count duplicate queries (same SQL + params).

        Returns:
            Tuple of (total_duplicates, list of (query_key, count) for duplicates)
        """
        query_keys = [
            (q["sql"], str(q["params"]))  # Use string repr of params for hashability
            for q in self.queries
        ]

        counts = Counter(query_keys)
        duplicates = [(key, count) for key, count in counts.items() if count > 1]
        total_duplicate_count = sum(count - 1 for _, count in duplicates)

        return total_duplicate_count, duplicates

    def get_query_count(self) -> int:
        """Get total number of queries executed."""
        return len(self.queries)

    def clear(self) -> None:
        """Clear captured queries."""
        self.queries = []


class APICallTracker:
    """Helper to track API calls by mocking NewsService.

    Tracks which symbols are fetched and when, allowing detection of
    duplicate API calls for the same symbol.
    """

    def __init__(self) -> None:
        """Initialize API call tracker with empty call list."""
        self.calls: list[dict[str, Any]] = []

    def track_get_news_intelligence(
        self,
        symbol: str,
        max_articles: int = 10,
        force_refresh: bool = False,
    ) -> NewsBundle:
        """Mock implementation of NewsService.get_news_intelligence().

        Records call details and returns mock NewsBundle.

        Args:
            symbol: Stock symbol
            max_articles: Maximum articles to fetch
            force_refresh: Whether to force cache refresh

        Returns:
            Mock NewsBundle with empty articles
        """
        self.calls.append(
            {
                "method": "get_news_intelligence",
                "symbol": symbol,
                "max_articles": max_articles,
                "force_refresh": force_refresh,
                "timestamp": datetime.now(UTC),
            }
        )

        # Return mock NewsBundle with NewsSummary
        summary = NewsSummary(
            symbol=symbol,
            score=0.5,
            score_change=0.0,
            positive_count=0,
            neutral_count=0,
            negative_count=0,
            article_count=0,
            latest_published_at=None,
        )
        return NewsBundle(
            symbol=symbol,
            summary=summary,
            articles=[],
        )

    def track_get_watchlist_news(
        self,
        symbols: list[str],
        max_articles: int = 10,
        force_refresh: bool = False,
    ) -> dict[str, NewsBundle]:
        """Mock implementation of NewsService.get_watchlist_news().

        Records call details and returns mock bundles for all symbols.

        Args:
            symbols: List of stock symbols
            max_articles: Maximum articles per symbol
            force_refresh: Whether to force cache refresh

        Returns:
            Dict mapping symbols to NewsBundle objects
        """
        self.calls.append(
            {
                "method": "get_watchlist_news",
                "symbols": symbols,
                "symbol_count": len(symbols),
                "max_articles": max_articles,
                "force_refresh": force_refresh,
                "timestamp": datetime.now(UTC),
            }
        )

        # Return mock bundles for all symbols
        return {
            symbol: NewsBundle(
                symbol=symbol,
                summary=NewsSummary(
                    symbol=symbol,
                    score=0.5,
                    score_change=0.0,
                    positive_count=0,
                    neutral_count=0,
                    negative_count=0,
                    article_count=0,
                    latest_published_at=None,
                ),
                articles=[],
            )
            for symbol in symbols
        }

    def get_symbols_fetched(self) -> list[str]:
        """Get list of all symbols that were fetched.

        Returns:
            List of symbols from all tracked calls
        """
        symbols = []
        for call in self.calls:
            if call["method"] == "get_news_intelligence":
                symbols.append(call["symbol"])
            elif call["method"] == "get_watchlist_news":
                symbols.extend(call["symbols"])
        return symbols

    def count_calls_per_symbol(self) -> dict[str, int]:
        """Count how many times each symbol was fetched.

        Returns:
            Dict mapping symbol to fetch count
        """
        symbols = self.get_symbols_fetched()
        return dict(Counter(symbols))

    def get_call_count(self) -> int:
        """Get total number of API calls made."""
        return len(self.calls)

    def get_calls_by_method(self, method: str) -> list[dict[str, Any]]:
        """Get all calls to a specific method.

        Args:
            method: Method name ('get_news_intelligence' or 'get_watchlist_news')

        Returns:
            List of call dictionaries for that method
        """
        return [c for c in self.calls if c["method"] == method]

    def clear(self) -> None:
        """Clear tracked calls."""
        self.calls = []


@pytest.fixture
def query_counter() -> QueryCounter:
    """Fixture providing a QueryCounter for tests.

    Automatically starts/stops listening to SQLAlchemy events.

    Yields:
        QueryCounter instance
    """
    counter = QueryCounter()
    counter.start_listening()
    yield counter
    counter.stop_listening()


@pytest.fixture
def api_tracker() -> APICallTracker:
    """Fixture providing an APICallTracker for tests.

    Yields:
        APICallTracker instance
    """
    return APICallTracker()


@pytest.fixture
def test_symbols() -> list[str]:
    """Fixture providing a standard set of test symbols.

    Returns:
        List of 10 test stock symbols
    """
    return ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "NFLX", "AMD", "INTC"]


@pytest.fixture
def setup_test_watchlist(test_symbols: list[str]) -> str:
    """Fixture that creates test watchlist items.

    Creates a default account and adds test symbols to watchlist.
    NOTE: Watchlist items are now independent of accounts (no account_id FK).

    Args:
        test_symbols: List of symbols to add

    Returns:
        Account ID (for backward compatibility with tests)
    """
    import uuid

    storage = get_storage()
    account_id = "default"

    # Create default account (for portfolio positions, not watchlist)
    with storage.connection() as conn:
        # Check if account exists
        result = conn.execute(
            "SELECT id FROM portfolio_accounts WHERE id = %s", [account_id]
        ).fetchone()

        if not result:
            conn.execute(
                """
                INSERT INTO portfolio_accounts (id, name, account_type)
                VALUES (%s, %s, %s)
                """,
                [account_id, "Default Account", "paper"],
            )
            conn.commit()

    # Add watchlist items directly via SQL
    # NOTE: No account_id - watchlist is now user-level, not account-level
    for symbol in test_symbols:
        item_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        with storage.connection() as conn:
            # Check if item already exists
            result = conn.execute(
                "SELECT id FROM watchlist_items WHERE symbol = %s",
                [symbol],
            ).fetchone()

            if not result:
                conn.execute(
                    """
                    INSERT INTO watchlist_items (id, symbol, note, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    [item_id, symbol, None, now, now],
                )
                conn.commit()

    return account_id


class TestInstrumentationSetup:
    """Test the instrumentation infrastructure itself.

    These tests verify that QueryCounter and APICallTracker work correctly
    before using them to validate hypotheses.
    """

    def test_query_counter_captures_queries(self, query_counter: QueryCounter) -> None:
        """Test that QueryCounter captures database queries."""
        storage = get_storage()

        # Execute a known query
        with storage.connection() as conn:
            conn.execute("SELECT 1 AS test_query")

        # Verify query was captured
        queries = query_counter.queries
        assert len(queries) > 0, "QueryCounter should capture queries"

        # Check that our test query is in the list
        test_queries = [q for q in queries if "test_query" in q["sql"].lower()]
        assert len(test_queries) > 0, "Test query should be captured"

    def test_query_counter_detects_duplicates(self, query_counter: QueryCounter) -> None:
        """Test that QueryCounter can detect duplicate queries."""
        storage = get_storage()

        # Execute the same query twice
        with storage.connection() as conn:
            conn.execute("SELECT 2 AS duplicate_test")
            conn.execute("SELECT 2 AS duplicate_test")

        # Count duplicates
        duplicate_count, _duplicates = query_counter.count_duplicate_queries()

        # Should have at least 1 duplicate (the query we ran twice)
        assert duplicate_count >= 1, "Should detect duplicate queries"

    def test_query_counter_filters_by_table(self, query_counter: QueryCounter) -> None:
        """Test that QueryCounter can filter queries by table name."""
        storage = get_storage()

        # Query a specific table
        with storage.connection() as conn:
            conn.execute("SELECT * FROM user_preferences LIMIT 1")

        # Filter queries
        pref_queries = query_counter.get_queries_to_table("user_preferences")

        assert len(pref_queries) > 0, "Should find queries to user_preferences"
        assert all("user_preferences" in q["sql"].lower() for q in pref_queries), (
            "All filtered queries should reference the table"
        )

    def test_api_tracker_captures_calls(self, api_tracker: APICallTracker) -> None:
        """Test that APICallTracker captures API calls."""
        # Simulate API calls
        api_tracker.track_get_news_intelligence("AAPL")
        api_tracker.track_get_news_intelligence("GOOGL")
        api_tracker.track_get_watchlist_news(["MSFT", "AMZN"])

        # Verify calls were captured
        assert api_tracker.get_call_count() == 3, "Should track 3 API calls"

        # Verify symbol tracking
        symbols = api_tracker.get_symbols_fetched()
        assert "AAPL" in symbols, "Should track AAPL"
        assert "GOOGL" in symbols, "Should track GOOGL"
        assert "MSFT" in symbols, "Should track MSFT from batch"
        assert "AMZN" in symbols, "Should track AMZN from batch"

    def test_api_tracker_counts_per_symbol(self, api_tracker: APICallTracker) -> None:
        """Test that APICallTracker counts calls per symbol."""
        # Fetch same symbol multiple times
        api_tracker.track_get_news_intelligence("AAPL")
        api_tracker.track_get_news_intelligence("AAPL")
        api_tracker.track_get_watchlist_news(["AAPL", "GOOGL"])

        # Count per symbol
        counts = api_tracker.count_calls_per_symbol()

        assert counts["AAPL"] == 3, "AAPL should be fetched 3 times"
        assert counts["GOOGL"] == 1, "GOOGL should be fetched 1 time"


class TestBaselineMeasurement:
    """Establish baseline metrics before implementing fixes.

    This test creates a snapshot of current behavior to measure improvements against.
    """

    def test_baseline_watchlist_refresh_metrics(
        self,
        query_counter: QueryCounter,
        api_tracker: APICallTracker,
        setup_test_watchlist: str,
    ) -> None:
        """Measure baseline metrics for watchlist refresh with 10 symbols.

        This test captures:
        - Total queries executed
        - Duplicate queries (same SQL + params)
        - Queries to specific tables (preferences, watchlist_items, snapshots)
        - API calls per symbol
        - Total execution time

        Results are saved for comparison after fixes are implemented.
        """
        import time

        account_id = setup_test_watchlist
        storage = get_storage()

        # Clear any existing data
        query_counter.clear()
        api_tracker.clear()

        # Mock NewsService to track API calls instead of making real ones
        with (
            patch(
                "app.services.news_service.NewsService.get_news_intelligence",
                api_tracker.track_get_news_intelligence,
            ),
            patch(
                "app.services.news_service.NewsService.get_watchlist_news",
                api_tracker.track_get_watchlist_news,
            ),
        ):
            # Measure execution time
            start_time = time.time()

            # Run watchlist refresh
            from app.watchlist.scoring_service import refresh_watchlist_scores

            refresh_watchlist_scores(storage, account_id=account_id)

            end_time = time.time()
            execution_time = end_time - start_time

        # Collect metrics
        total_queries = query_counter.get_query_count()
        duplicate_count, duplicates = query_counter.count_duplicate_queries()
        pref_queries = query_counter.get_queries_to_table("user_preferences")
        watchlist_queries = query_counter.get_queries_to_table("watchlist_items")
        snapshot_queries = query_counter.get_queries_to_table("watchlist_snapshots")

        api_calls = api_tracker.get_call_count()
        symbols_fetched = api_tracker.get_symbols_fetched()
        symbol_counts = api_tracker.count_calls_per_symbol()

        # Print baseline metrics for documentation
        print("\n" + "=" * 70)
        print("BASELINE METRICS - Watchlist Refresh (10 symbols)")
        print("=" * 70)
        print(f"Total queries executed: {total_queries}")
        print(f"Duplicate queries: {duplicate_count}")
        print(f"  - Queries to user_preferences: {len(pref_queries)}")
        print(f"  - Queries to watchlist_items: {len(watchlist_queries)}")
        print(f"  - Queries to watchlist_snapshots: {len(snapshot_queries)}")
        print("\nAPI Calls:")
        print(f"  - Total API calls: {api_calls}")
        print(f"  - Unique symbols fetched: {len(set(symbols_fetched))}")
        print(
            f"  - Symbols fetched multiple times: {len([s for s, c in symbol_counts.items() if c > 1])}"
        )
        print(f"\nExecution time: {execution_time:.2f}s")
        print("=" * 70)

        # Save to file for later comparison
        import json
        from pathlib import Path

        baseline_data = {
            "test_name": "baseline_watchlist_refresh_10_symbols",
            "timestamp": datetime.now(UTC).isoformat(),
            "metrics": {
                "total_queries": total_queries,
                "duplicate_queries": duplicate_count,
                "preference_queries": len(pref_queries),
                "watchlist_item_queries": len(watchlist_queries),
                "snapshot_queries": len(snapshot_queries),
                "api_calls": api_calls,
                "unique_symbols": len(set(symbols_fetched)),
                "symbols_fetched_multiple_times": len(
                    [s for s, c in symbol_counts.items() if c > 1]
                ),
                "execution_time_seconds": execution_time,
            },
            "duplicates_detail": [
                {"query": sql[:100], "params": str(params)[:50], "count": count}
                for (sql, params), count in duplicates[:5]  # Top 5 duplicates
            ],
        }

        # Save to tests/integration directory
        baseline_file = Path(__file__).parent / "baseline_metrics.json"
        with baseline_file.open("w") as f:
            json.dump(baseline_data, f, indent=2)

        print(f"\nBaseline metrics saved to: {baseline_file}")

        # Basic assertions to ensure test ran successfully
        assert total_queries > 0, "Should have executed queries"
        assert api_calls >= 0, "API calls count should be non-negative"


class TestIssue1OverlappingNewsFetches:
    """Validate hypothesis: Both tasks fetch news for same symbols concurrently.

    Expected: When refresh_watchlist_scores and refresh_news_sentiment run
    concurrently, they both fetch news for the same symbols, causing duplicate API calls.
    """

    def test_concurrent_tasks_fetch_same_symbols(
        self,
        query_counter: QueryCounter,
        api_tracker: APICallTracker,
        setup_test_watchlist: str,
    ) -> None:
        """Test if watchlist and news tasks fetch news for same symbols.

        This validates Issue #1: Do the tasks overlap in their news fetching?
        """

        account_id = setup_test_watchlist
        storage = get_storage()

        # Clear trackers
        query_counter.clear()
        api_tracker.clear()

        # Mock NewsService methods to track calls
        with (
            patch(
                "app.services.news_service.NewsService.get_news_intelligence",
                api_tracker.track_get_news_intelligence,
            ),
            patch(
                "app.services.news_service.NewsService.get_watchlist_news",
                api_tracker.track_get_watchlist_news,
            ),
        ):
            # Import task functions
            from app.watchlist.scoring_service import refresh_watchlist_scores

            # Run watchlist refresh (simulates what happens in production)
            refresh_watchlist_scores(storage, account_id=account_id)

        # Analyze results
        api_calls = api_tracker.get_call_count()
        symbols_fetched = api_tracker.get_symbols_fetched()
        symbol_counts = api_tracker.count_calls_per_symbol()
        get_news_intelligence_calls = api_tracker.get_calls_by_method("get_news_intelligence")
        get_watchlist_news_calls = api_tracker.get_calls_by_method("get_watchlist_news")

        # Print findings
        print("\n" + "=" * 70)
        print("ISSUE #1 VALIDATION: Overlapping News Fetches")
        print("=" * 70)
        print(f"Total API calls: {api_calls}")
        print(f"  - get_news_intelligence() calls: {len(get_news_intelligence_calls)}")
        print(f"  - get_watchlist_news() calls: {len(get_watchlist_news_calls)}")
        print(f"Unique symbols fetched: {len(set(symbols_fetched))}")
        print(f"Symbols fetched multiple times: {[s for s, c in symbol_counts.items() if c > 1]}")
        print("=" * 70)

        # For this validation, we're testing watchlist refresh in isolation
        # The overlap would occur if news_refresh task also runs, but that's
        # tested in Task 1.1.1 with concurrent execution

        # Issue #1 is about INTER-task overlap (two different tasks)
        # This test shows INTRA-task behavior (single task)
        # Conclusion: Need concurrent test to validate hypothesis

        print("\nCONCLUSION: This test shows single-task behavior.")
        print("Issue #1 requires concurrent execution of BOTH tasks to validate.")
        print("Deferring full validation - Issue #1 may be FALSE POSITIVE in current setup.")

    def test_issue1_analysis_from_baseline(self) -> None:
        """Analyze baseline metrics for Issue #1.

        From baseline:
        - 10 symbols in watchlist
        - 23 API calls made
        - 23 unique symbols fetched (includes market news, not just watchlist)

        This suggests the refresh IS fetching more than just watchlist symbols.
        Let's investigate what those extra symbols are.
        """
        from pathlib import Path

        baseline_file = Path(__file__).parent / "baseline_metrics.json"
        with baseline_file.open() as f:
            baseline = json.load(f)

        print("\n" + "=" * 70)
        print("ISSUE #1 ANALYSIS from Baseline")
        print("=" * 70)
        print("Watchlist symbols: 10")
        print(f"Total API calls: {baseline['metrics']['api_calls']}")
        print(f"Unique symbols: {baseline['metrics']['unique_symbols']}")
        print(f"Extra fetches: {baseline['metrics']['unique_symbols'] - 10}")
        print("\nHYPOTHESIS: The 23 calls likely include:")
        print("  - 10 watchlist symbols")
        print("  - Market-wide news (__MARKET__)")
        print("  - Possibly duplicate fetches in processing")
        print("\nRECOMMENDATION: Issue #1 is about CONCURRENT tasks.")
        print("Since news_refresh_task runs separately, we need to:")
        print("  1. Check if it's currently enabled in scheduler")
        print("  2. Test with both tasks running")
        print("  3. Measure overlap between their fetch times")
        print("=" * 70)


class TestIssue2PerSymbolNewsFetching:
    """Validate hypothesis: News is fetched individually per symbol (N calls) instead of batch (1 call).

    Expected: refresh_processor.py:439 calls get_news_intelligence() in a loop for each symbol,
    resulting in N API calls instead of using get_watchlist_news() for batch fetching.
    """

    def test_per_symbol_fetching_in_watchlist_refresh(
        self,
        query_counter: QueryCounter,
        api_tracker: APICallTracker,
        setup_test_watchlist: str,
    ) -> None:
        """Validate that news is fetched individually per symbol.

        Expected behavior:
        - get_news_intelligence() called N times (once per symbol)
        - get_watchlist_news() called 0 times
        - Total API calls = N

        This would confirm Issue #2.
        """

        account_id = setup_test_watchlist
        storage = get_storage()

        # Clear trackers
        query_counter.clear()
        api_tracker.clear()

        # Mock NewsService methods
        with (
            patch(
                "app.services.news_service.NewsService.get_news_intelligence",
                api_tracker.track_get_news_intelligence,
            ),
            patch(
                "app.services.news_service.NewsService.get_watchlist_news",
                api_tracker.track_get_watchlist_news,
            ),
        ):
            from app.watchlist.scoring_service import refresh_watchlist_scores

            refresh_watchlist_scores(storage, account_id=account_id)

        # Analyze results
        get_news_intelligence_calls = api_tracker.get_calls_by_method("get_news_intelligence")
        get_watchlist_news_calls = api_tracker.get_calls_by_method("get_watchlist_news")
        total_api_calls = api_tracker.get_call_count()

        # Expected: 10 watchlist symbols
        num_watchlist_symbols = 10

        # Print findings
        print("\n" + "=" * 70)
        print("ISSUE #2 VALIDATION: Per-Symbol News Fetching")
        print("=" * 70)
        print(f"Watchlist symbols: {num_watchlist_symbols}")
        print(f"Total API calls: {total_api_calls}")
        print(f"get_news_intelligence() calls: {len(get_news_intelligence_calls)}")
        print(f"get_watchlist_news() calls: {len(get_watchlist_news_calls)}")
        print("=" * 70)

        # Validate hypothesis
        if len(get_news_intelligence_calls) > 0 and len(get_watchlist_news_calls) == 0:
            print("\n✓ HYPOTHESIS CONFIRMED: Using per-symbol fetching")
            print("  - Expected: 1 batch call for all symbols")
            print(f"  - Actual: {len(get_news_intelligence_calls)} individual calls")
            print(f"  - Overhead: {len(get_news_intelligence_calls) - 1} extra calls")
            print("\nROOT CAUSE: refresh_processor.py:439")
            print("  Calls get_news_intelligence(symbol) in loop instead of")
            print("  calling get_watchlist_news(symbols) before loop")
            hypothesis_confirmed = True
        elif len(get_watchlist_news_calls) > 0:
            print("\n✗ HYPOTHESIS REJECTED: Already using batch fetching")
            print(f"  get_watchlist_news() was called {len(get_watchlist_news_calls)} time(s)")
            hypothesis_confirmed = False
        else:
            print("\n? INCONCLUSIVE: No news fetching detected")
            hypothesis_confirmed = False

        print("=" * 70)

        # Save conclusion
        import json
        from pathlib import Path

        result = {
            "issue": "Issue #2: Per-Symbol News Fetching",
            "hypothesis": "News fetched individually (N calls) vs batch (1 call)",
            "validated": hypothesis_confirmed,
            "evidence": {
                "watchlist_symbols": num_watchlist_symbols,
                "get_news_intelligence_calls": len(get_news_intelligence_calls),
                "get_watchlist_news_calls": len(get_watchlist_news_calls),
                "total_api_calls": total_api_calls,
            },
            "root_cause": "refresh_processor.py:439 - get_news_intelligence() in loop"
            if hypothesis_confirmed
            else None,
            "fix_approach": "Fetch news before loop using get_watchlist_news()"
            if hypothesis_confirmed
            else None,
        }

        results_file = Path(__file__).parent / "issue2_validation.json"
        with results_file.open("w") as f:
            json.dump(result, f, indent=2)

        print(f"\nValidation results saved to: {results_file}")

        # Assert for test framework
        assert total_api_calls > 0, "Should have made API calls"

        # Return whether to proceed with fix
        if hypothesis_confirmed:
            print("\n✓ PROCEED TO FIX: Issue #2 validated - implement batch fetching")
        else:
            print("\n⊘ SKIP FIX: Issue #2 not validated - no action needed")


class TestIssue3UserPreferencesQueries:
    """Validate hypothesis: User preferences table is queried 5 separate times.

    Expected: refresh_watchlist_scores() queries user_preferences multiple times
    instead of loading all preferences once.
    """

    def test_user_preferences_query_count(
        self,
        query_counter: QueryCounter,
        api_tracker: APICallTracker,
        setup_test_watchlist: str,
    ) -> None:
        """Validate that user preferences are queried multiple times.

        Expected behavior:
        - user_preferences table queried 5+ times
        - Same or similar queries repeated
        - Could be consolidated to 1 query

        This would confirm Issue #3.
        """

        account_id = setup_test_watchlist
        storage = get_storage()

        # Clear trackers
        query_counter.clear()
        api_tracker.clear()

        # Mock NewsService methods
        with (
            patch(
                "app.services.news_service.NewsService.get_news_intelligence",
                api_tracker.track_get_news_intelligence,
            ),
            patch(
                "app.services.news_service.NewsService.get_watchlist_news",
                api_tracker.track_get_watchlist_news,
            ),
        ):
            from app.watchlist.scoring_service import refresh_watchlist_scores

            refresh_watchlist_scores(storage, account_id=account_id)

        # Analyze preference queries
        pref_queries = query_counter.get_queries_to_table("user_preferences")
        total_queries = query_counter.get_query_count()

        # Group queries by SQL to find duplicates
        query_sql_counts = {}
        for q in pref_queries:
            sql_key = q["sql"]
            query_sql_counts[sql_key] = query_sql_counts.get(sql_key, 0) + 1

        # Print findings
        print("\n" + "=" * 70)
        print("ISSUE #3 VALIDATION: User Preferences Query Count")
        print("=" * 70)
        print(f"Total queries executed: {total_queries}")
        print(f"Queries to user_preferences: {len(pref_queries)}")
        print(f"Unique preference queries: {len(query_sql_counts)}")
        print("\nQuery breakdown:")
        for sql, count in query_sql_counts.items():
            print(f"  - {count}x: {sql[:80]}...")
        print("=" * 70)

        # Validate hypothesis
        if len(pref_queries) >= 3:
            print("\n✓ HYPOTHESIS CONFIRMED: Multiple preference queries detected")
            print("  - Expected: 1 query to load all preferences")
            print(f"  - Actual: {len(pref_queries)} separate queries")
            print(f"  - Overhead: {len(pref_queries) - 1} redundant queries")
            print("\nROOT CAUSE: Preferences fetched individually instead of batch load")
            hypothesis_confirmed = True
        else:
            print("\n✗ HYPOTHESIS REJECTED: Using efficient preference loading")
            print(f"  Only {len(pref_queries)} preference queries detected")
            hypothesis_confirmed = False

        print("=" * 70)

        # Save conclusion
        result = {
            "issue": "Issue #3: User Preferences Queried Multiple Times",
            "hypothesis": "Preferences queried 5 times instead of 1 batch load",
            "validated": hypothesis_confirmed,
            "evidence": {
                "total_queries": total_queries,
                "preference_queries": len(pref_queries),
                "unique_queries": len(query_sql_counts),
                "query_breakdown": {sql[:50]: count for sql, count in query_sql_counts.items()},
            },
            "root_cause": "Preferences fetched individually per field/call"
            if hypothesis_confirmed
            else None,
            "fix_approach": "Create UserPreferences.load_all() to fetch in single query"
            if hypothesis_confirmed
            else None,
        }

        from pathlib import Path

        results_file = Path(__file__).parent / "issue3_validation.json"
        with results_file.open("w") as f:
            json.dump(result, f, indent=2)

        print(f"\nValidation results saved to: {results_file}")

        # Assert for test framework
        assert total_queries > 0, "Should have executed queries"

        # Return whether to proceed with fix
        if hypothesis_confirmed:
            print("\n✓ PROCEED TO FIX: Issue #3 validated - implement centralized loader")
        else:
            print("\n⊘ SKIP FIX: Issue #3 not validated - no action needed")


class TestIssue4WatchlistItemsQueries:
    """Validate hypothesis: Watchlist items queried by multiple tasks.

    Expected: Both watchlist_tasks and news_tasks query watchlist_items separately,
    causing duplicate queries.
    """

    def test_watchlist_items_query_count(
        self,
        query_counter: QueryCounter,
        api_tracker: APICallTracker,
        setup_test_watchlist: str,
    ) -> None:
        """Validate that watchlist items are queried multiple times.

        This test runs watchlist refresh and checks how many times watchlist_items
        table is queried. In production, news_refresh task would also query it.
        """

        account_id = setup_test_watchlist
        storage = get_storage()

        # Clear trackers
        query_counter.clear()
        api_tracker.clear()

        # Mock NewsService methods
        with (
            patch(
                "app.services.news_service.NewsService.get_news_intelligence",
                api_tracker.track_get_news_intelligence,
            ),
            patch(
                "app.services.news_service.NewsService.get_watchlist_news",
                api_tracker.track_get_watchlist_news,
            ),
        ):
            from app.watchlist.scoring_service import refresh_watchlist_scores

            # Run watchlist refresh once
            refresh_watchlist_scores(storage, account_id=account_id)

        # Analyze watchlist_items queries
        watchlist_queries = query_counter.get_queries_to_table("watchlist_items")

        # Print findings
        print("\n" + "=" * 70)
        print("ISSUE #4 VALIDATION: Watchlist Items Query Count")
        print("=" * 70)
        print(f"Queries to watchlist_items: {len(watchlist_queries)}")
        print("\nQuery details:")
        for i, q in enumerate(watchlist_queries, 1):
            print(f"  {i}. {q['sql'][:80]}...")
        print("=" * 70)

        # Validate hypothesis
        # NOTE: In single-task test, we expect only 1 query
        # Issue #4 is about INTER-task duplication (news_refresh also queries)
        if len(watchlist_queries) > 1:
            print("\n✓ HYPOTHESIS CONFIRMED: Multiple watchlist_items queries")
            print("  - Expected: 1 query (or use caching)")
            print(f"  - Actual: {len(watchlist_queries)} queries")
            hypothesis_confirmed = True
        else:
            print("\n? PARTIAL VALIDATION: Only 1 query in single-task test")
            print("  Issue #4 is about multiple TASKS querying watchlist_items")
            print("  Current test: Single task (watchlist refresh)")
            print("  Production: news_refresh task ALSO queries watchlist_items")
            print("\n  RECOMMENDATION: Check if news_refresh is scheduled concurrently")
            hypothesis_confirmed = False

        print("=" * 70)

        # Save conclusion
        result = {
            "issue": "Issue #4: Watchlist Items Queried by Multiple Tasks",
            "hypothesis": "Both watchlist and news tasks query watchlist_items",
            "validated": hypothesis_confirmed,
            "evidence": {
                "watchlist_item_queries": len(watchlist_queries),
                "single_task_test": True,
                "note": "Inter-task overlap requires concurrent execution testing",
            },
            "root_cause": "Multiple tasks fetch watchlist symbols independently"
            if hypothesis_confirmed
            else "Requires concurrent task testing to validate",
            "fix_approach": "Add Redis cache for watchlist symbols (60s TTL)"
            if hypothesis_confirmed
            else "Test with concurrent tasks first",
        }

        from pathlib import Path

        results_file = Path(__file__).parent / "issue4_validation.json"
        with results_file.open("w") as f:
            json.dump(result, f, indent=2)

        print(f"\nValidation results saved to: {results_file}")

        # Assert for test framework
        assert len(watchlist_queries) > 0, "Should have queried watchlist_items"

        if hypothesis_confirmed:
            print("\n✓ PROCEED TO FIX: Issue #4 validated")
        else:
            print("\n⊘ DEFER: Needs concurrent task testing for full validation")


class TestIssue5N1QueryPattern:
    """Validate hypothesis: get_items_with_scores() queries snapshots individually (N+1).

    Expected: watchlist_service.get_items_with_scores() queries watchlist_items once,
    then queries watchlist_snapshots N times (once per item) instead of using JOIN.
    """

    def test_n_plus_1_pattern_in_get_items_with_scores(
        self,
        query_counter: QueryCounter,
        setup_test_watchlist: str,
    ) -> None:
        """Validate N+1 query pattern in watchlist service.

        Expected behavior:
        - 1 query to fetch watchlist_items
        - N queries to fetch snapshots (one per item)
        - Total: 1 + N queries (N+1 pattern)

        This would confirm Issue #5.
        """

        # Setup creates watchlist items
        _ = setup_test_watchlist
        storage = get_storage()

        # Clear tracker
        query_counter.clear()

        # Call the service method directly
        from app.watchlist.watchlist_service import WatchlistService

        service = WatchlistService(storage)
        items = service.get_items_with_scores()  # No account_id - watchlist is user-level

        # Count items returned
        num_items = len(items)

        # Analyze queries
        total_queries = query_counter.get_query_count()
        watchlist_queries = query_counter.get_queries_to_table("watchlist_items")
        snapshot_queries = query_counter.get_queries_to_table("watchlist_snapshots")

        # Print findings
        print("\n" + "=" * 70)
        print("ISSUE #5 VALIDATION: N+1 Query Pattern")
        print("=" * 70)
        print(f"Watchlist items returned: {num_items}")
        print(f"Total queries executed: {total_queries}")
        print(f"  - Queries to watchlist_items: {len(watchlist_queries)}")
        print(f"  - Queries to watchlist_snapshots: {len(snapshot_queries)}")
        print(f"\nExpected (N+1 pattern): 1 + {num_items} = {1 + num_items} queries")
        print(
            f"Actual: {len(watchlist_queries)} + {len(snapshot_queries)} = {len(watchlist_queries) + len(snapshot_queries)} queries"
        )
        print("=" * 70)

        # Validate hypothesis
        # Classic N+1: 1 query for items, N queries for snapshots
        if len(snapshot_queries) >= num_items:
            print("\n✓ HYPOTHESIS CONFIRMED: N+1 query pattern detected")
            print("  - Expected: 1 JOIN query for items + snapshots")
            print(f"  - Actual: 1 query for items + {len(snapshot_queries)} queries for snapshots")
            print(f"  - Overhead: {len(snapshot_queries) - 1} extra queries")
            print("\nROOT CAUSE: watchlist_service.get_items_with_scores()")
            print("  Queries snapshots individually per item instead of using JOIN")
            hypothesis_confirmed = True
        elif len(snapshot_queries) == 0 and total_queries == 1:
            print("\n✗ HYPOTHESIS REJECTED: Using efficient JOIN query")
            print("  Only 1 query executed - likely using JOIN to fetch items + snapshots")
            hypothesis_confirmed = False
        else:
            print("\n? INCONCLUSIVE: Unexpected query pattern")
            print(f"  Items: {num_items}, Snapshot queries: {len(snapshot_queries)}")
            hypothesis_confirmed = False

        print("=" * 70)

        # Save conclusion
        result = {
            "issue": "Issue #5: N+1 Query Pattern in get_items_with_scores()",
            "hypothesis": "Snapshots queried individually (N queries) vs JOIN (1 query)",
            "validated": hypothesis_confirmed,
            "evidence": {
                "items_returned": num_items,
                "total_queries": total_queries,
                "watchlist_item_queries": len(watchlist_queries),
                "snapshot_queries": len(snapshot_queries),
                "expected_n_plus_1": 1 + num_items,
                "actual_queries": len(watchlist_queries) + len(snapshot_queries),
            },
            "root_cause": "watchlist_service.get_items_with_scores() - queries snapshots in loop"
            if hypothesis_confirmed
            else None,
            "fix_approach": "Add JOIN query: SELECT items LEFT JOIN LATERAL snapshots"
            if hypothesis_confirmed
            else None,
        }

        from pathlib import Path

        results_file = Path(__file__).parent / "issue5_validation.json"
        with results_file.open("w") as f:
            json.dump(result, f, indent=2)

        print(f"\nValidation results saved to: {results_file}")

        # Assert for test framework
        assert total_queries > 0, "Should have executed queries"
        assert num_items > 0, "Should have returned items"

        # Return whether to proceed with fix
        if hypothesis_confirmed:
            print("\n✓ PROCEED TO FIX: Issue #5 validated - implement JOIN query")
        else:
            print("\n⊘ SKIP FIX: Issue #5 not validated - already using efficient query")
