"""Tests for portfolio covariance matrix calculations (GAP-020).

These tests verify the correct implementation of portfolio risk calculation
using covariance matrix instead of the incorrect weighted-average approach.
"""

import math
from datetime import date

import pytest

from app.analytics.covariance import (
    align_returns,
    calculate_daily_returns,
    calculate_pairwise_covariance,
    calculate_portfolio_volatility_from_covariance,
    calculate_volatility,
    calculate_weight_hash,
)


class TestPairwiseCovariance:
    """Tests for pairwise covariance calculation."""

    def test_identical_returns(self) -> None:
        """Identical returns should have correlation of 1.0."""
        returns1 = [0.01, 0.02, -0.01, 0.015, -0.005]
        returns2 = [0.01, 0.02, -0.01, 0.015, -0.005]

        cov, corr = calculate_pairwise_covariance(returns1, returns2)

        assert corr == pytest.approx(1.0, abs=0.001)
        assert cov > 0  # Same direction, positive covariance

    def test_opposite_returns(self) -> None:
        """Opposite returns should have correlation of -1.0."""
        returns1 = [0.01, 0.02, -0.01, 0.015, -0.005]
        returns2 = [-0.01, -0.02, 0.01, -0.015, 0.005]

        cov, corr = calculate_pairwise_covariance(returns1, returns2)

        assert corr == pytest.approx(-1.0, abs=0.001)
        assert cov < 0  # Opposite direction, negative covariance

    def test_uncorrelated_returns(self) -> None:
        """Random uncorrelated returns should have low correlation."""
        # These are designed to be roughly uncorrelated
        returns1 = [0.01, -0.01, 0.01, -0.01, 0.01]
        returns2 = [0.01, 0.01, -0.01, -0.01, 0.00]

        cov, corr = calculate_pairwise_covariance(returns1, returns2)

        # Correlation should be close to 0 (but not exactly due to limited samples)
        assert abs(corr) < 0.5

    def test_empty_returns(self) -> None:
        """Empty returns should return zero covariance and correlation."""
        cov, corr = calculate_pairwise_covariance([], [])

        assert cov == 0.0
        assert corr == 0.0

    def test_single_return(self) -> None:
        """Single return should return zero (need 2+ for variance)."""
        cov, corr = calculate_pairwise_covariance([0.01], [0.02])

        assert cov == 0.0
        assert corr == 0.0


class TestAlignReturns:
    """Tests for aligning return series by date."""

    def test_overlapping_dates(self) -> None:
        """Overlapping dates should be aligned correctly."""
        returns1 = [
            (date(2024, 1, 1), 0.01),
            (date(2024, 1, 2), 0.02),
            (date(2024, 1, 3), 0.03),
        ]
        returns2 = [
            (date(2024, 1, 2), 0.05),
            (date(2024, 1, 3), 0.06),
            (date(2024, 1, 4), 0.07),
        ]

        aligned1, aligned2 = align_returns(returns1, returns2)

        assert len(aligned1) == 2
        assert len(aligned2) == 2
        assert aligned1 == [0.02, 0.03]
        assert aligned2 == [0.05, 0.06]

    def test_no_overlap(self) -> None:
        """No overlapping dates should return empty lists."""
        returns1 = [(date(2024, 1, 1), 0.01)]
        returns2 = [(date(2024, 1, 5), 0.05)]

        aligned1, aligned2 = align_returns(returns1, returns2)

        assert aligned1 == []
        assert aligned2 == []


class TestVolatility:
    """Tests for volatility calculation."""

    def test_constant_returns(self) -> None:
        """Constant returns should have zero volatility."""
        returns = [0.01, 0.01, 0.01, 0.01, 0.01]

        vol = calculate_volatility(returns, annualize=False)

        assert vol == 0.0

    def test_variable_returns(self) -> None:
        """Variable returns should have positive volatility."""
        returns = [0.01, -0.01, 0.02, -0.02, 0.01]

        vol = calculate_volatility(returns, annualize=False)

        assert vol > 0

    def test_annualization(self) -> None:
        """Annualization should multiply by sqrt(252)."""
        returns = [0.01, -0.01, 0.02, -0.02, 0.01]

        daily_vol = calculate_volatility(returns, annualize=False)
        annual_vol = calculate_volatility(returns, annualize=True)

        assert annual_vol == pytest.approx(daily_vol * math.sqrt(252), abs=0.0001)


class TestPortfolioVolatilityFromCovariance:
    """Tests for portfolio volatility calculation using covariance matrix."""

    def test_single_asset(self) -> None:
        """Single asset portfolio volatility equals asset volatility."""
        weights = {"AAPL": 1.0}
        # Daily variance of 0.0004 = daily vol of 0.02 = annual vol of ~0.316
        cov_matrix = {("AAPL", "AAPL"): 0.0004}

        portfolio_vol = calculate_portfolio_volatility_from_covariance(weights, cov_matrix)

        expected_annual_vol = math.sqrt(0.0004) * math.sqrt(252)
        assert portfolio_vol == pytest.approx(expected_annual_vol, abs=0.01)

    def test_two_uncorrelated_assets(self) -> None:
        """Two uncorrelated assets should reduce portfolio volatility."""
        weights = {"AAPL": 0.5, "GOOGL": 0.5}
        # Both have same variance, but zero covariance
        cov_matrix = {
            ("AAPL", "AAPL"): 0.0004,
            ("GOOGL", "GOOGL"): 0.0004,
            ("AAPL", "GOOGL"): 0.0,
            ("GOOGL", "AAPL"): 0.0,
        }

        portfolio_vol = calculate_portfolio_volatility_from_covariance(weights, cov_matrix)

        # For uncorrelated assets: portfolio_var = 0.5^2 * var_A + 0.5^2 * var_B
        # = 0.25 * 0.0004 + 0.25 * 0.0004 = 0.0002
        # Portfolio daily vol = sqrt(0.0002) ≈ 0.0141
        # Annual vol = 0.0141 * sqrt(252) ≈ 0.224
        expected_annual_vol = math.sqrt(0.5**2 * 0.0004 + 0.5**2 * 0.0004) * math.sqrt(252)
        assert portfolio_vol == pytest.approx(expected_annual_vol, abs=0.01)

    def test_two_perfectly_correlated_assets(self) -> None:
        """Two perfectly correlated assets should not reduce portfolio volatility."""
        weights = {"AAPL": 0.5, "GOOGL": 0.5}
        # Same variance and perfect correlation (covariance = var)
        cov_matrix = {
            ("AAPL", "AAPL"): 0.0004,
            ("GOOGL", "GOOGL"): 0.0004,
            ("AAPL", "GOOGL"): 0.0004,  # cov = vol1 * vol2 * corr = sqrt(var) * sqrt(var) * 1 = var
            ("GOOGL", "AAPL"): 0.0004,
        }

        portfolio_vol = calculate_portfolio_volatility_from_covariance(weights, cov_matrix)

        # For perfectly correlated: portfolio_var = (w1*std1 + w2*std2)^2
        # = (0.5*0.02 + 0.5*0.02)^2 = 0.0004
        # This equals single asset variance, so vol should be same as single asset
        single_asset_vol = math.sqrt(0.0004) * math.sqrt(252)
        assert portfolio_vol == pytest.approx(single_asset_vol, abs=0.01)

    def test_diversification_benefit(self) -> None:
        """Portfolio of uncorrelated assets should have lower vol than weighted avg."""
        weights = {"AAPL": 0.5, "GOOGL": 0.5}

        # Individual vols (annualized): sqrt(0.0004 * 252) ≈ 0.316 each
        # Weighted average vol = 0.5 * 0.316 + 0.5 * 0.316 = 0.316

        # Uncorrelated case
        cov_matrix_uncorrelated = {
            ("AAPL", "AAPL"): 0.0004,
            ("GOOGL", "GOOGL"): 0.0004,
            ("AAPL", "GOOGL"): 0.0,
            ("GOOGL", "AAPL"): 0.0,
        }

        portfolio_vol_uncorrelated = calculate_portfolio_volatility_from_covariance(
            weights, cov_matrix_uncorrelated
        )

        weighted_avg_vol = math.sqrt(0.0004) * math.sqrt(252)

        # Portfolio vol should be lower than weighted average due to diversification
        assert portfolio_vol_uncorrelated < weighted_avg_vol


class TestWeightHash:
    """Tests for portfolio weight hashing."""

    def test_consistent_hash(self) -> None:
        """Same weights should produce same hash."""
        weights1 = {"AAPL": 0.5, "GOOGL": 0.5}
        weights2 = {"AAPL": 0.5, "GOOGL": 0.5}

        hash1 = calculate_weight_hash(weights1)
        hash2 = calculate_weight_hash(weights2)

        assert hash1 == hash2

    def test_order_independent(self) -> None:
        """Different order should produce same hash."""
        weights1 = {"AAPL": 0.5, "GOOGL": 0.5}
        weights2 = {"GOOGL": 0.5, "AAPL": 0.5}

        hash1 = calculate_weight_hash(weights1)
        hash2 = calculate_weight_hash(weights2)

        assert hash1 == hash2

    def test_different_weights_different_hash(self) -> None:
        """Different weights should produce different hash."""
        weights1 = {"AAPL": 0.5, "GOOGL": 0.5}
        weights2 = {"AAPL": 0.6, "GOOGL": 0.4}

        hash1 = calculate_weight_hash(weights1)
        hash2 = calculate_weight_hash(weights2)

        assert hash1 != hash2
