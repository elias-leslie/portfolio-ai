from app.portfolio._price_cache import cache_prices, get_cached_prices
from app.portfolio.models import PriceData
from app.storage import get_storage


def test_first_index_quote_creates_parent_and_preserves_existing_symbol_metadata():
    storage = get_storage()
    with storage.connection() as conn:
        conn.execute(
            "INSERT INTO symbols (symbol,company_name) VALUES ('CACHEKNOWN','Known company')"
        )
        conn.commit()
    prices = {
        "^CACHEFIRST": PriceData(symbol="^CACHEFIRST", price=20, source="test"),
        "CACHEKNOWN": PriceData(symbol="CACHEKNOWN", price=100, source="test"),
    }
    cache_prices(prices, storage)
    cache_prices(prices, storage)
    cached = get_cached_prices(list(prices), storage, None)
    assert cached["^CACHEFIRST"].price == 20
    with storage.connection() as conn:
        row = conn.execute("SELECT company_name FROM symbols WHERE symbol='CACHEKNOWN'").fetchone()
        assert row is not None
        assert row[0] == "Known company"
