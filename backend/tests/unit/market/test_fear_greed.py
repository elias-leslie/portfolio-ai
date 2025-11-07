"""Unit tests for Fear & Greed Index calculation engine."""

from app.market.fear_greed import FearGreedEngine


class MockStorage:
    """Mock storage for testing."""

    def __init__(self, historical_data: dict[str, list[float]]) -> None:
        self.historical_data = historical_data

    def connection(self):
        """Mock connection context manager."""
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query: str):
        """Mock execute method."""
        # Extract field name from query
        for field in self.historical_data:
            if field in query:
                return MockResult(self.historical_data[field])
        return MockResult([])

    def commit(self) -> None:
        """Mock commit."""
        pass


class MockResult:
    """Mock database result."""

    def __init__(self, values: list[float]) -> None:
        self.values = values

    def fetchall(self):
        """Return values as rows."""
        return [(v,) for v in self.values]


class TestFearGreedEngine:
    """Test Fear & Greed calculation engine."""

    def test_calculate_percentile_normal(self) -> None:
        """Test percentile calculation with normal values."""
        storage = MockStorage({})
        engine = FearGreedEngine(storage)

        # Value in middle of range
        historical = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = engine.calculate_percentile(30.0, historical, invert=False)

        # Percentile should be valid (0-100)
        assert 0 <= result <= 100

    def test_calculate_percentile_inverted(self) -> None:
        """Test percentile calculation with inversion (for fear signals)."""
        storage = MockStorage({})
        engine = FearGreedEngine(storage)

        # High VIX = high fear = LOW score
        historical = [10.0, 15.0, 20.0, 25.0, 30.0]
        result = engine.calculate_percentile(30.0, historical, invert=True)

        assert result <= 20  # High value inverted = low percentile

    def test_calculate_percentile_clamping(self) -> None:
        """Test percentile clamping to 0-100 range."""
        storage = MockStorage({})
        engine = FearGreedEngine(storage)

        # Extreme low value - should be near bottom of range
        historical = [50.0, 60.0, 70.0, 80.0, 90.0]
        result = engine.calculate_percentile(10.0, historical, invert=False)
        assert result <= 20  # Very low compared to historical

        # Extreme high value - should be near top of range
        result = engine.calculate_percentile(100.0, historical, invert=False)
        assert result >= 80  # Very high compared to historical

    def test_score_momentum_above_sma(self) -> None:
        """Test momentum scoring when price is above 200-day MA."""
        storage = MockStorage({})
        engine = FearGreedEngine(storage)

        # 10% above SMA_200
        score = engine.score_momentum(spy_close=110.0, spy_sma_200=100.0)

        assert score > 50  # Above SMA = bullish = high score
        assert score <= 100

    def test_score_momentum_below_sma(self) -> None:
        """Test momentum scoring when price is below 200-day MA."""
        storage = MockStorage({})
        engine = FearGreedEngine(storage)

        # 10% below SMA_200
        score = engine.score_momentum(spy_close=90.0, spy_sma_200=100.0)

        assert score < 50  # Below SMA = bearish = low score
        assert score >= 0

    def test_score_momentum_at_sma(self) -> None:
        """Test momentum scoring when price is at 200-day MA."""
        storage = MockStorage({})
        engine = FearGreedEngine(storage)

        score = engine.score_momentum(spy_close=100.0, spy_sma_200=100.0)

        assert 45 <= score <= 55  # At SMA = neutral = ~50

    def test_compose_score_all_signals(self) -> None:
        """Test score composition with all 5 signals present."""
        storage = MockStorage({})
        engine = FearGreedEngine(storage)

        components = {
            "vix_pct": 30,  # Low fear
            "momentum_pct": 70,  # Bullish
            "rsi_pct": 60,  # Slightly overbought
            "pcr_pct": 40,  # Moderate
            "credit_pct": 50,  # Neutral
        }

        score = engine.compose_score(components)

        # Equal weighted average
        expected = (30 + 70 + 60 + 40 + 50) / 5
        assert abs(score - expected) < 0.5

    def test_compose_score_missing_signal(self) -> None:
        """Test score composition with missing signal (defaults to 50)."""
        storage = MockStorage({})
        engine = FearGreedEngine(storage)

        components = {
            "vix_pct": 30,
            "momentum_pct": 70,
            "rsi_pct": 60,
            "credit_pct": 50,
            # pcr_pct missing (Put/Call not available)
        }

        score = engine.compose_score(components)

        # Missing signal defaults to 50 (neutral)
        expected = (30 + 70 + 60 + 50 + 50) / 5
        assert abs(score - expected) < 0.5

    def test_assign_label_extreme_fear(self) -> None:
        """Test label assignment for extreme fear."""
        storage = MockStorage({})
        engine = FearGreedEngine(storage)

        assert engine.assign_label(0.0) == "Extreme Fear"
        assert engine.assign_label(20.0) == "Extreme Fear"
        assert engine.assign_label(24.9) == "Extreme Fear"

    def test_assign_label_fear(self) -> None:
        """Test label assignment for fear."""
        storage = MockStorage({})
        engine = FearGreedEngine(storage)

        assert engine.assign_label(25.0) == "Fear"
        assert engine.assign_label(35.0) == "Fear"
        assert engine.assign_label(44.9) == "Fear"

    def test_assign_label_neutral(self) -> None:
        """Test label assignment for neutral."""
        storage = MockStorage({})
        engine = FearGreedEngine(storage)

        assert engine.assign_label(45.0) == "Neutral"
        assert engine.assign_label(50.0) == "Neutral"
        assert engine.assign_label(54.9) == "Neutral"

    def test_assign_label_greed(self) -> None:
        """Test label assignment for greed."""
        storage = MockStorage({})
        engine = FearGreedEngine(storage)

        assert engine.assign_label(55.0) == "Greed"
        assert engine.assign_label(65.0) == "Greed"
        assert engine.assign_label(74.9) == "Greed"

    def test_assign_label_extreme_greed(self) -> None:
        """Test label assignment for extreme greed."""
        storage = MockStorage({})
        engine = FearGreedEngine(storage)

        assert engine.assign_label(75.0) == "Extreme Greed"
        assert engine.assign_label(85.0) == "Extreme Greed"
        assert engine.assign_label(100.0) == "Extreme Greed"

    def test_score_signals_with_historical_data(self) -> None:
        """Test signal scoring with mocked historical data."""
        historical_data = {
            "vix_close": [15.0, 18.0, 20.0, 22.0, 25.0],  # VIX history
            "hy_spread": [2.5, 3.0, 3.5, 4.0, 4.5],  # Credit spread history
        }
        storage = MockStorage(historical_data)
        engine = FearGreedEngine(storage)

        inputs = {
            "vix_close": 20.0,
            "spy_close": 680.0,
            "spy_sma_200": 650.0,
            "rsi_14": 55.0,
            "hy_spread": 3.5,
        }

        scores = engine.score_signals(inputs, window_days=252)

        # All scores should be valid percentiles (0-100)
        assert "vix_pct" in scores
        assert 0 <= scores["vix_pct"] <= 100

        assert "momentum_pct" in scores
        assert 0 <= scores["momentum_pct"] <= 100

        assert "rsi_pct" in scores
        assert scores["rsi_pct"] == 55  # RSI used directly

        assert "credit_pct" in scores
        assert 0 <= scores["credit_pct"] <= 100
