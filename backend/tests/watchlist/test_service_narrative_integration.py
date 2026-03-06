"""Test narrative generation integration in watchlist refresh flow."""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.portfolio.models import PriceData
from app.storage import PortfolioStorage
from app.watchlist.service import refresh_watchlist_scores
from tests.test_support.news import build_empty_news_service


@pytest.fixture
def storage() -> Iterator[PortfolioStorage]:
    """Create a PortfolioStorage instance for testing."""
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


class TestNarrativeGenerationIntegration:
    """Test that narrative generation is called during watchlist refresh."""

    def test_refresh_generates_narrative_for_buy_signal(self, storage: PortfolioStorage) -> None:
        """Verify refresh flow calls narrative generation and stores results."""
        # Create watchlist item with good technical setup
        with storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO watchlist_items (id, symbol, metadata)
                VALUES (?, ?, ?)
                """,
                ["narrative-test-1", "NVDA", "{}"],
            )
            conn.commit()

        # Mock price fetcher to return good price data
        nvda_price = PriceData(
            symbol="NVDA",
            price=202.0,
            beta=1.3,
            volatility=0.25,
            source="test",
        )

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_price_data.return_value = {"NVDA": nvda_price}
        mock_news_service = build_empty_news_service()

        # Insert technical indicators for BUY signal
        with storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO technical_indicators (
                    symbol, date, rsi_14, sma_50, sma_200, macd, macd_signal,
                    ema_20, atr_14, calculated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    "NVDA",
                    "2025-11-02",
                    55.0,  # Good RSI (not extreme)
                    195.0,  # SMA-50
                    180.0,  # SMA-200
                    2.5,  # Positive MACD
                    1.8,  # MACD signal
                    200.0,  # EMA-20 (below current price = uptrend)
                    7.0,  # ATR-14
                    datetime.now(UTC),
                ],
            )
            # Insert historical price data for swing calculations
            conn.execute(
                """
                INSERT INTO day_bars (symbol, date, open, high, low, close, volume, vwap, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ["NVDA", "2025-11-01", 200.0, 205.0, 198.0, 201.0, 1000000, 201.0, "test"],
            )
            conn.execute(
                """
                INSERT INTO day_bars (symbol, date, open, high, low, close, volume, vwap, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ["NVDA", "2025-10-31", 195.0, 200.0, 193.0, 195.0, 900000, 195.0, "test"],
            )
            conn.commit()

        # Execute refresh
        result = refresh_watchlist_scores(
            storage,
            price_fetcher=mock_fetcher,
            news_service=mock_news_service,
        )

        assert result["processed"] == 1
        assert "NVDA" in result["symbols"]

        # Verify narrative fields were populated
        snapshots = storage.query(
            """
            SELECT signal_type, signal_strength, narrative_headline,
                   recommended_style, style_confidence, optimal_holding_period, risk_level
            FROM watchlist_snapshots
            WHERE item_id = 'narrative-test-1'
            ORDER BY fetched_at DESC
            LIMIT 1
            """
        )

        assert snapshots.height == 1
        snapshot_dict = snapshots.to_dicts()[0]

        # Verify signal classification
        assert snapshot_dict["signal_type"] in ["BUY", "HOLD", "AVOID"]
        assert snapshot_dict["signal_strength"] is not None
        assert 0 <= snapshot_dict["signal_strength"] <= 10

        # Verify narrative generated
        assert snapshot_dict["narrative_headline"] is not None
        assert len(snapshot_dict["narrative_headline"]) > 0

        # Verify trading style classified
        assert snapshot_dict["recommended_style"] in [
            "Index",
            "Trend",
            "Value",
            "Swing",
            "Event",
        ]
        assert snapshot_dict["style_confidence"] is not None
        assert 0 <= snapshot_dict["style_confidence"] <= 10
        assert snapshot_dict["optimal_holding_period"] is not None
        assert snapshot_dict["risk_level"] in ["Low", "Medium-Low", "Medium", "High"]

    def test_refresh_handles_missing_fundamentals_gracefully(
        self, storage: PortfolioStorage
    ) -> None:
        """Verify refresh continues if fundamentals cannot be fetched."""
        # Create watchlist item
        with storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO watchlist_items (id, symbol, metadata)
                VALUES (?, ?, ?)
                """,
                ["narrative-test-2", "UNKNOWN", "{}"],
            )
            conn.commit()

        # Mock price fetcher
        unknown_price = PriceData(
            symbol="UNKNOWN",
            price=100.0,
            beta=None,
            volatility=None,
            source="test",
        )

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_price_data.return_value = {"UNKNOWN": unknown_price}
        mock_news_service = build_empty_news_service()

        # Execute refresh (no technical indicators or fundamentals)
        result = refresh_watchlist_scores(
            storage,
            price_fetcher=mock_fetcher,
            news_service=mock_news_service,
        )

        # Should still process, but with limited narrative data
        assert result["processed"] == 1

        snapshots = storage.query(
            """
            SELECT signal_type, narrative_headline, company_health
            FROM watchlist_snapshots
            WHERE item_id = 'narrative-test-2'
            ORDER BY fetched_at DESC
            LIMIT 1
            """
        )

        assert snapshots.height == 1
        snapshot_dict = snapshots.to_dicts()[0]

        # Should have basic signal (likely HOLD or AVOID due to missing data)
        assert snapshot_dict["signal_type"] in ["BUY", "HOLD", "AVOID"]

        # Headline may be generic but should exist
        assert snapshot_dict["narrative_headline"] is not None

        # Company health may be None (fundamentals unavailable)
        # This is acceptable - narrative should handle gracefully
