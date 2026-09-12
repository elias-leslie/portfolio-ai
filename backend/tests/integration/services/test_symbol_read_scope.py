import uuid
from datetime import UTC, datetime

from app.storage import get_storage
from app.watchlist.watchlist_repository import WatchlistRepository


def test_symbol_snapshot_query_limits_enrichment_input_without_changing_full_watchlist():
    repository = WatchlistRepository(get_storage())
    for symbol in ("AAPL", "MSFT"):
        repository.create_item(str(uuid.uuid4()), symbol, None, datetime.now(UTC).isoformat())
    assert set(repository.get_all_items_with_snapshots()["symbol"]) == {"AAPL", "MSFT"}
    assert repository.get_all_items_with_snapshots(symbol="aapl")["symbol"].to_list() == ["AAPL"]
    assert repository.get_all_items_with_snapshots(symbol="UNKNOWN").is_empty()
