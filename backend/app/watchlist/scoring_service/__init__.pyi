"""Type stubs for scoring_service lazy imports."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from redis import Redis

from app.storage import PortfolioStorage
from app.watchlist.models import WatchlistItem

# Helper functions
def _is_stale(last_update: datetime | None, max_age_minutes: int) -> bool: ...

# Aggregator functions
def aggregate_results(
    results: list[dict[str, Any]],
    failed: list[str],
) -> dict[str, Any]: ...
def process_all_symbols(
    storage: PortfolioStorage,
    account_id: str,
    symbols: list[str],
    watchlist_items: dict[str, WatchlistItem],
    news_map: dict[str, Any],
    prices_map: dict[str, Any],
    technical_map: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]: ...

# Batch loader functions
def fetch_news_batch(storage: PortfolioStorage, symbols: list[str]) -> dict[str, Any]: ...
def fetch_prices_in_batches(
    storage: PortfolioStorage,
    symbols: list[str],
    batch_size: int = 100,
) -> dict[str, Any]: ...
def load_latest_technical(
    storage: PortfolioStorage,
    symbols: list[str],
) -> dict[str, Any]: ...
def load_watchlist_items(
    storage: PortfolioStorage,
    account_id: str,
) -> dict[str, WatchlistItem]: ...
def trigger_auto_backfill(storage: PortfolioStorage, symbols: list[str]) -> None: ...

# Context functions
def initialize_scoring_context(
    storage: PortfolioStorage,
    account_id: str,
) -> tuple[dict[str, WatchlistItem], dict[str, Any], dict[str, Any], dict[str, Any]]: ...

# Processor functions
def process_single_symbol(
    storage: PortfolioStorage,
    account_id: str,
    symbol: str,
    watchlist_item: WatchlistItem,
    news_data: Any,
    price_data: Any,
    technical_data: Any,
) -> dict[str, Any]: ...

# Redis tracker functions
def complete_refresh(account_id: str, stats: dict[str, Any]) -> None: ...
def get_redis_client() -> Redis[bytes]: ...
def init_refresh_status(account_id: str, total_symbols: int) -> None: ...
def update_progress(account_id: str, processed: int) -> None: ...

# Main scoring service function
def refresh_watchlist_scores(
    storage: PortfolioStorage,
    *,
    account_id: str | None = None,
    price_fetcher: Any = None,
    batch_size: int = 20,
    batch_delay_seconds: float = 2.0,
    symbols_filter: list[str] | None = None,
) -> dict[str, Any]: ...
