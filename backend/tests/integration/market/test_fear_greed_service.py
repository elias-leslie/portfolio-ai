"""Integration tests for Fear & Greed Index service."""

from datetime import date, timedelta

import pytest

from app.market.fear_greed_service import FearGreedService
from app.storage import get_storage


@pytest.fixture
def storage():
    """Get storage instance."""
    return get_storage()


@pytest.fixture
def service(storage):
    """Create FearGreedService instance."""
    return FearGreedService(storage)


class TestFearGreedServiceIntegration:
    """Integration tests for FearGreedService."""

    def test_persist_inputs(self, service, storage) -> None:
        """Test persisting input signals to database."""
        test_date = date(2025, 11, 1)
        inputs = {
            "vix_close": 18.5,
            "spy_close": 680.0,
            "spy_sma_200": 650.0,
            "rsi_14": 55.0,
            "hy_spread": 3.2,
            "source_map": {"vix": "FRED", "hy_spread": "FRED", "spy": "Database"},
        }

        # Persist inputs
        service.persist_inputs(test_date, inputs)

        # Verify data was saved
        with storage.connection() as conn:
            result = conn.execute(
                "SELECT vix_close, spy_close, rsi_14 FROM fear_greed_inputs WHERE as_of_date = %s",
                (test_date,),
            )
            row = result.fetchone()

        assert row is not None
        assert float(row[0]) == 18.5  # vix_close
        assert float(row[1]) == 680.0  # spy_close
        assert float(row[2]) == 55.0  # rsi_14

    def test_persist_components(self, service, storage) -> None:
        """Test persisting component scores to database."""
        test_date = date(2025, 11, 1)
        components = {
            "vix_pct": 45,
            "momentum_pct": 65,
            "rsi_pct": 55,
            "pcr_pct": 50,
            "credit_pct": 40,
        }

        # Persist components
        service.persist_components(test_date, components, window_days=252)

        # Verify data was saved
        with storage.connection() as conn:
            result = conn.execute(
                "SELECT vix_pct, momentum_pct, rsi_pct FROM fear_greed_components WHERE as_of_date = %s",
                (test_date,),
            )
            row = result.fetchone()

        assert row is not None
        assert row[0] == 45  # vix_pct
        assert row[1] == 65  # momentum_pct
        assert row[2] == 55  # rsi_pct

    def test_persist_score(self, service, storage) -> None:
        """Test persisting final score to database."""
        test_date = date(2025, 11, 1)
        result_data = {
            "score": 52.5,
            "label": "Greed",
            "previous_score": 48.0,
            "score_change": 4.5,
            "signal_count": 5,
        }

        # Persist score
        service.persist_score(test_date, result_data)

        # Verify data was saved
        with storage.connection() as conn:
            result = conn.execute(
                "SELECT score, label, previous_score, score_change, signal_count FROM fear_greed_daily WHERE as_of_date = %s",
                (test_date,),
            )
            row = result.fetchone()

        assert row is not None
        assert float(row[0]) == 52.5  # score
        assert row[1] == "Greed"  # label
        assert float(row[2]) == 48.0  # previous_score
        assert float(row[3]) == 4.5  # score_change
        assert row[4] == 5  # signal_count

    def test_get_latest(self, service, storage) -> None:
        """Test retrieving latest Fear & Greed reading."""
        # First ensure we have data
        test_date = date.today() - timedelta(days=1)
        result_data = {
            "score": 42.0,
            "label": "Fear",
            "previous_score": None,
            "score_change": None,
            "signal_count": 4,
        }
        service.persist_score(test_date, result_data)

        # Retrieve latest
        latest = service.get_latest()

        assert latest is not None
        assert "score" in latest
        assert "label" in latest
        assert latest["label"] in ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"]

    def test_get_by_date(self, service, storage) -> None:
        """Test retrieving Fear & Greed reading for specific date."""
        test_date = date(2025, 11, 1)
        result_data = {
            "score": 55.0,
            "label": "Greed",
            "previous_score": None,
            "score_change": None,
            "signal_count": 4,
        }
        service.persist_score(test_date, result_data)

        # Retrieve by date
        reading = service.get_by_date(test_date)

        assert reading is not None
        assert reading["score"] == 55.0
        assert reading["label"] == "Greed"

    def test_get_history(self, service, storage) -> None:
        """Test retrieving Fear & Greed history."""
        # Insert multiple readings
        for i in range(5):
            test_date = date(2025, 11, 1) + timedelta(days=i)
            result_data = {
                "score": 40.0 + i * 5,
                "label": "Fear" if i < 2 else "Neutral",
                "previous_score": None,
                "score_change": None,
                "signal_count": 4,
            }
            service.persist_score(test_date, result_data)

        # Retrieve history
        start = date(2025, 11, 1)
        end = date(2025, 11, 5)
        history = service.get_history(start, end)

        assert len(history) >= 5
        assert all("score" in reading for reading in history)
        assert all("label" in reading for reading in history)

    def test_idempotent_writes(self, service, storage) -> None:
        """Test that writing same data twice doesn't create duplicates."""
        test_date = date(2025, 11, 1)
        result_data = {
            "score": 50.0,
            "label": "Neutral",
            "previous_score": None,
            "score_change": None,
            "signal_count": 4,
        }

        # Write twice
        service.persist_score(test_date, result_data)
        service.persist_score(test_date, result_data)

        # Should only have one row
        with storage.connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM fear_greed_daily WHERE as_of_date = %s",
                (test_date,),
            )
            count = result.fetchone()[0]

        assert count == 1
