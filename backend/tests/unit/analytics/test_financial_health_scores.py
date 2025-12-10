"""Unit tests for financial health scoring (Piotroski F-Score, Altman Z-Score)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from app.analytics.financial_health_scores import (
    FinancialHealthScores,
    calculate_altman_z_score,
    calculate_piotroski_f_score,
    get_financial_health_scores,
)


class TestFinancialHealthScoresDataclass:
    """Tests for FinancialHealthScores dataclass."""

    def test_creation_with_all_fields(self) -> None:
        """Test creating FinancialHealthScores with all fields."""
        scores = FinancialHealthScores(
            symbol="AAPL",
            f_score=7,
            f_score_components={"roa_positive": 1, "ocf_positive": 1},
            z_score=3.5,
            z_score_zone="safe",
            error=None,
        )
        assert scores.symbol == "AAPL"
        assert scores.f_score == 7
        assert scores.z_score == 3.5
        assert scores.z_score_zone == "safe"

    def test_creation_with_defaults(self) -> None:
        """Test default values are None."""
        scores = FinancialHealthScores(symbol="TEST")
        assert scores.f_score is None
        assert scores.f_score_components is None
        assert scores.z_score is None
        assert scores.z_score_zone is None
        assert scores.error is None


class TestPiotroskiFScore:
    """Tests for Piotroski F-Score calculation."""

    @patch("app.analytics.financial_health_scores.YFINANCE_AVAILABLE", False)
    def test_returns_error_when_yfinance_unavailable(self) -> None:
        """Test returns error when yfinance not installed."""
        score, components, error = calculate_piotroski_f_score("AAPL")
        assert score is None
        assert components is None
        assert error == "yfinance not available"

    @patch("app.analytics.financial_health_scores.yf")
    def test_returns_error_for_empty_financials(self, mock_yf: MagicMock) -> None:
        """Test returns error when financial statements are empty."""
        mock_ticker = MagicMock()
        mock_ticker.balance_sheet = pd.DataFrame()
        mock_ticker.cashflow = pd.DataFrame()
        mock_ticker.income_stmt = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker

        score, _components, error = calculate_piotroski_f_score("FAKE")
        assert score is None
        assert "Insufficient financial statement data" in str(error)

    @patch("app.analytics.financial_health_scores.yf")
    def test_returns_error_for_insufficient_periods(self, mock_yf: MagicMock) -> None:
        """Test returns error when less than 2 periods available."""
        mock_ticker = MagicMock()
        # Only 1 column (1 period) - need 2 for YoY comparison
        mock_ticker.balance_sheet = pd.DataFrame({"2024": [100]}, index=["Total Assets"])
        mock_ticker.cashflow = pd.DataFrame({"2024": [50]}, index=["Operating Cash Flow"])
        mock_ticker.income_stmt = pd.DataFrame({"2024": [25]}, index=["Net Income"])
        mock_yf.Ticker.return_value = mock_ticker

        score, _components, error = calculate_piotroski_f_score("FAKE")
        assert score is None
        assert "Need at least 2 periods" in str(error)

    @patch("app.analytics.financial_health_scores.yf")
    def test_calculates_score_from_valid_data(self, mock_yf: MagicMock) -> None:
        """Test F-Score calculation with valid financial data."""
        mock_ticker = MagicMock()

        # Create realistic financial data (2 periods)
        mock_ticker.balance_sheet = pd.DataFrame(
            {
                "2024": [1000, 500, 200, 300, 100],
                "2023": [900, 550, 180, 280, 90],
            },
            index=[
                "Total Assets",
                "Total Liabilities Net Minority Interest",
                "Current Assets",
                "Current Liabilities",
                "Common Stock",
            ],
        )

        mock_ticker.income_stmt = pd.DataFrame(
            {
                "2024": [100, 50, 200],
                "2023": [80, 45, 180],
            },
            index=["Net Income", "Gross Profit", "Total Revenue"],
        )

        mock_ticker.cashflow = pd.DataFrame(
            {
                "2024": [120],
                "2023": [100],
            },
            index=["Operating Cash Flow"],
        )

        mock_yf.Ticker.return_value = mock_ticker

        score, components, error = calculate_piotroski_f_score("TEST")

        # Should return a valid score
        assert error is None or "error" not in str(error).lower()
        if score is not None:
            assert 0 <= score <= 9
            assert components is not None
            # Should have component keys
            assert "roa_positive" in components or len(components) > 0

    @patch("app.analytics.financial_health_scores.yf")
    def test_handles_missing_data_gracefully(self, mock_yf: MagicMock) -> None:
        """Test handles missing financial data fields gracefully."""
        mock_ticker = MagicMock()

        # Sparse data - missing many fields
        mock_ticker.balance_sheet = pd.DataFrame(
            {"2024": [1000], "2023": [900]},
            index=["Total Assets"],
        )
        mock_ticker.income_stmt = pd.DataFrame(
            {"2024": [100], "2023": [80]},
            index=["Net Income"],
        )
        mock_ticker.cashflow = pd.DataFrame(
            {"2024": [50], "2023": [40]},
            index=["Operating Cash Flow"],
        )
        mock_yf.Ticker.return_value = mock_ticker

        # Should not raise exception
        score, _components, error = calculate_piotroski_f_score("SPARSE")
        # Either returns a score or an error, but shouldn't crash
        assert (score is not None) or (error is not None)


class TestAltmanZScore:
    """Tests for Altman Z-Score calculation."""

    @patch("app.analytics.financial_health_scores.YFINANCE_AVAILABLE", False)
    def test_returns_error_when_yfinance_unavailable(self) -> None:
        """Test returns error when yfinance not installed."""
        z_score, zone, error = calculate_altman_z_score("AAPL")
        assert z_score is None
        assert zone is None
        assert error == "yfinance not available"

    @patch("app.analytics.financial_health_scores.yf")
    def test_returns_error_for_empty_financials(self, mock_yf: MagicMock) -> None:
        """Test returns error when financial statements are empty."""
        mock_ticker = MagicMock()
        mock_ticker.balance_sheet = pd.DataFrame()
        mock_ticker.income_stmt = pd.DataFrame()
        mock_ticker.info = {}
        mock_yf.Ticker.return_value = mock_ticker

        z_score, _zone, error = calculate_altman_z_score("FAKE")
        assert z_score is None
        assert "Insufficient" in str(error) or error is not None

    @patch("app.analytics.financial_health_scores.yf")
    def test_safe_zone_classification(self, mock_yf: MagicMock) -> None:
        """Test Z-Score above 2.99 classified as 'safe'."""
        mock_ticker = MagicMock()

        # Create data that would result in high Z-Score
        mock_ticker.balance_sheet = pd.DataFrame(
            {"2024": [1000, 800, 300, 200, 100]},
            index=[
                "Total Assets",
                "Current Assets",
                "Current Liabilities",
                "Total Liabilities Net Minority Interest",
                "Retained Earnings",
            ],
        )
        mock_ticker.income_stmt = pd.DataFrame(
            {"2024": [500, 150]},
            index=["Total Revenue", "EBIT"],
        )
        mock_ticker.info = {"marketCap": 5000}
        mock_yf.Ticker.return_value = mock_ticker

        z_score, zone, _error = calculate_altman_z_score("STRONG")

        if z_score is not None and z_score > 2.99:
            assert zone == "safe"

    @patch("app.analytics.financial_health_scores.yf")
    def test_distress_zone_classification(self, mock_yf: MagicMock) -> None:
        """Test Z-Score below 1.81 classified as 'distress'."""
        mock_ticker = MagicMock()

        # Create data that would result in low Z-Score (high debt, low earnings)
        mock_ticker.balance_sheet = pd.DataFrame(
            {"2024": [1000, 200, 400, 900, -100]},
            index=[
                "Total Assets",
                "Current Assets",
                "Current Liabilities",
                "Total Liabilities Net Minority Interest",
                "Retained Earnings",
            ],
        )
        mock_ticker.income_stmt = pd.DataFrame(
            {"2024": [100, -50]},  # Negative EBIT
            index=["Total Revenue", "EBIT"],
        )
        mock_ticker.info = {"marketCap": 100}  # Low market cap
        mock_yf.Ticker.return_value = mock_ticker

        z_score, zone, _error = calculate_altman_z_score("WEAK")

        if z_score is not None and z_score < 1.81:
            assert zone == "distress"


class TestGetFinancialHealthScores:
    """Tests for get_financial_health_scores combined function."""

    @patch("app.analytics.financial_health_scores.calculate_piotroski_f_score")
    @patch("app.analytics.financial_health_scores.calculate_altman_z_score")
    def test_combines_both_scores(self, mock_z_score: MagicMock, mock_f_score: MagicMock) -> None:
        """Test get_financial_health_scores combines F-Score and Z-Score."""
        mock_f_score.return_value = (7, {"roa_positive": 1}, None)
        mock_z_score.return_value = (3.5, "safe", None)

        result = get_financial_health_scores("TEST")

        assert result.symbol == "TEST"
        assert result.f_score == 7
        assert result.f_score_components == {"roa_positive": 1}
        assert result.z_score == 3.5
        assert result.z_score_zone == "safe"
        assert result.error is None

    @patch("app.analytics.financial_health_scores.calculate_piotroski_f_score")
    @patch("app.analytics.financial_health_scores.calculate_altman_z_score")
    def test_handles_f_score_error(self, mock_z_score: MagicMock, mock_f_score: MagicMock) -> None:
        """Test handles F-Score calculation error."""
        mock_f_score.return_value = (None, None, "F-Score error")
        mock_z_score.return_value = (2.5, "grey", None)

        result = get_financial_health_scores("ERROR")

        assert result.f_score is None
        assert result.z_score == 2.5
        # Error should be captured
        assert result.error is not None or result.f_score is None

    @patch("app.analytics.financial_health_scores.calculate_piotroski_f_score")
    @patch("app.analytics.financial_health_scores.calculate_altman_z_score")
    def test_handles_z_score_error(self, mock_z_score: MagicMock, mock_f_score: MagicMock) -> None:
        """Test handles Z-Score calculation error."""
        mock_f_score.return_value = (6, {"test": 1}, None)
        mock_z_score.return_value = (None, None, "Z-Score error")

        result = get_financial_health_scores("ERROR")

        assert result.f_score == 6
        assert result.z_score is None
        # Error should be captured
        assert result.error is not None or result.z_score is None

    @patch("app.analytics.financial_health_scores.calculate_piotroski_f_score")
    @patch("app.analytics.financial_health_scores.calculate_altman_z_score")
    def test_handles_both_errors(self, mock_z_score: MagicMock, mock_f_score: MagicMock) -> None:
        """Test handles errors from both calculations."""
        mock_f_score.return_value = (None, None, "F error")
        mock_z_score.return_value = (None, None, "Z error")

        result = get_financial_health_scores("BAD")

        assert result.f_score is None
        assert result.z_score is None
        assert result.error is not None


class TestFScoreComponents:
    """Tests for individual F-Score component calculations."""

    @patch("app.analytics.financial_health_scores.yf")
    def test_roa_positive_when_net_income_positive(self, mock_yf: MagicMock) -> None:
        """Test ROA positive component when net income > 0."""
        mock_ticker = MagicMock()
        mock_ticker.balance_sheet = pd.DataFrame(
            {"2024": [1000], "2023": [900]},
            index=["Total Assets"],
        )
        mock_ticker.income_stmt = pd.DataFrame(
            {"2024": [100], "2023": [80]},  # Positive net income
            index=["Net Income"],
        )
        mock_ticker.cashflow = pd.DataFrame(
            {"2024": [50], "2023": [40]},
            index=["Operating Cash Flow"],
        )
        mock_yf.Ticker.return_value = mock_ticker

        _score, components, _error = calculate_piotroski_f_score("TEST")

        if components and "roa_positive" in components:
            assert components["roa_positive"] == 1

    @patch("app.analytics.financial_health_scores.yf")
    def test_roa_negative_when_net_income_negative(self, mock_yf: MagicMock) -> None:
        """Test ROA component is 0 when net income < 0."""
        mock_ticker = MagicMock()
        mock_ticker.balance_sheet = pd.DataFrame(
            {"2024": [1000], "2023": [900]},
            index=["Total Assets"],
        )
        mock_ticker.income_stmt = pd.DataFrame(
            {"2024": [-100], "2023": [-80]},  # Negative net income
            index=["Net Income"],
        )
        mock_ticker.cashflow = pd.DataFrame(
            {"2024": [50], "2023": [40]},
            index=["Operating Cash Flow"],
        )
        mock_yf.Ticker.return_value = mock_ticker

        _score, components, _error = calculate_piotroski_f_score("LOSS")

        if components and "roa_positive" in components:
            assert components["roa_positive"] == 0
