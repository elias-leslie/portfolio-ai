from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from app.portfolio.models import PriceData
from app.storage import PortfolioStorage
from app.watchlist.scoring_service import refresh_watchlist_scores
from app.watchlist.watchlist_service import _normalize_recent_news_payload
from tests.test_support.news import build_empty_news_service


class StubPriceFetcher:
    def __init__(self, data: dict[str, PriceData]) -> None:
        self.data = data

    def fetch_price_data(self, symbols: list[str]) -> dict[str, PriceData]:
        return {symbol: self.data[symbol] for symbol in symbols if symbol in self.data}


@pytest.fixture
def storage() -> Iterator[PortfolioStorage]:
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "watchlist.db"

    from app.storage.connection import ConnectionManager
    from app.storage.ingestion import IngestionManager
    from app.storage.metadata import MetadataManager
    from app.storage.queries import QueryManager
    from app.storage.schema import SchemaManager

    storage_inst = PortfolioStorage.__new__(PortfolioStorage)
    storage_inst.connection_mgr = ConnectionManager()
    storage_inst.schema_mgr = SchemaManager(storage_inst.connection_mgr)
    storage_inst.metadata_mgr = MetadataManager(storage_inst.connection_mgr)
    storage_inst.ingestion_mgr = IngestionManager(
        storage_inst.connection_mgr, storage_inst.metadata_mgr
    )
    storage_inst.query_mgr = QueryManager(storage_inst.connection_mgr)
    storage_inst.schema_mgr.ensure_schema()

    yield storage_inst

    if db_path.exists():
        db_path.unlink()
    Path(temp_dir).rmdir()


def _insert_user_preferences(
    storage: PortfolioStorage, price_weight: float, technical_weight: float
) -> None:
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (
                id, risk_tolerance, allow_long, allow_short, allow_options,
                allow_crypto, allow_futures, max_position_size_pct,
                watchlist_refresh_minutes, watchlist_auto_expand,
                watchlist_price_weight, watchlist_technical_weight,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "user-1",
                5,
                True,
                False,
                False,
                False,
                False,
                10.0,
                5,
                False,
                price_weight,
                technical_weight,
                datetime.now(UTC),
                datetime.now(UTC),
            ],
        )


def _insert_watchlist_item(storage: PortfolioStorage, item_id: str, symbol: str) -> None:
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO watchlist_items (id, symbol, metadata)
            VALUES (?, ?, ?)
            """,
            [item_id, symbol, json.dumps({})],
        )
        conn.commit()


def _insert_day_bars(storage: PortfolioStorage, symbol: str, closes: list[float]) -> None:
    start_date = datetime.now(UTC) - timedelta(days=len(closes) + 5)
    rows = []
    for idx, close in enumerate(closes):
        current_date = (start_date + timedelta(days=idx)).date()
        rows.append(
            {
                "symbol": symbol,
                "date": current_date,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": 500_000,
                "vwap": close,
                "source": "test",
                "ingest_run_id": None,
            }
        )

    storage.insert_dataframe("day_bars", pl.DataFrame(rows), mode="append")


def _insert_technical(storage: PortfolioStorage, symbol: str, rsi: float) -> None:
    storage.insert_dataframe(
        "technical_indicators",
        pl.DataFrame(
            [
                {
                    "symbol": symbol,
                    "date": datetime.now(UTC).date(),
                    "rsi_14": rsi,
                    "macd": None,
                    "macd_signal": None,
                    "macd_histogram": None,
                    "bb_upper": None,
                    "bb_middle": None,
                    "bb_lower": None,
                    "sma_20": None,
                    "sma_50": 175.0,
                    "sma_200": 170.0,
                    "ema_20": None,
                    "ema_50": None,
                    "ema_200": None,
                    "atr_14": None,
                    "stoch_k": None,
                    "stoch_d": None,
                    "calculated_at": datetime.now(UTC),
                }
            ]
        ),
        mode="append",
    )


def _insert_account(storage: PortfolioStorage, account_id: str) -> None:
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO portfolio_accounts (id, name, account_type)
            VALUES (?, ?, ?)
            """,
            [account_id, "Primary", "Taxable"],
        )
        conn.commit()


def test_refresh_watchlist_scores_persists_snapshots(storage: PortfolioStorage) -> None:
    _insert_user_preferences(storage, price_weight=40.0, technical_weight=60.0)
    _insert_watchlist_item(storage, "item-1", "AAPL")
    _insert_day_bars(
        storage,
        "AAPL",
        [150.0, 152.0, 154.0, 156.0, 158.0, 160.0, 163.0, 165.0, 167.0, 170.0],
    )
    _insert_day_bars(
        storage,
        "SPY",
        [100.0, 101.0, 102.0, 101.5, 103.0, 104.0, 103.5, 105.0, 106.0, 107.0],
    )
    _insert_technical(storage, "AAPL", 55.0)

    price_data = PriceData(symbol="AAPL", price=162.0, source="test")
    fetcher = StubPriceFetcher({"AAPL": price_data})
    news_service = build_empty_news_service()

    result = refresh_watchlist_scores(storage, price_fetcher=fetcher, news_service=news_service)

    assert result["processed"] == 1
    assert result["symbols"] == ["AAPL"]

    df = storage.query("SELECT * FROM watchlist_snapshots WHERE item_id = ?", ["item-1"])
    assert df.height == 1
    row = df.to_dicts()[0]
    assert row["overall_score"] is not None
    assert row["price"] == pytest.approx(162.0)
    assert row["raw_metrics"] is not None


def test_normalize_recent_news_payload_backfills_vendor_and_publisher() -> None:
    payload = {
        "summary": {"symbol": "AAPL"},
        "articles": [
            {
                "headline": "Example",
                "vendor": None,
                "source": None,
                "raw": {
                    "vendor": "finnhub",
                    "raw": {
                        "vendor": "finnhub",
                        "source": {"title": "Example Publisher"},
                    },
                },
            }
        ],
    }

    normalized = _normalize_recent_news_payload(payload)
    assert normalized["articles"][0]["vendor"] == "finnhub"
    assert normalized["articles"][0]["source"] == "Example Publisher"
    assert normalized["articles"][0]["publisher"] == "Example Publisher"
