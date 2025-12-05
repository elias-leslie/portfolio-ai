"""Unit tests for trading rules loader module."""

import time

from app.rules.loader import (
    _CACHE_TTL_SECONDS,
    get_rules,
    reload_rules,
)
from app.rules.models import (
    CatalystImpact,
    ComplianceRules,
    FeeRules,
    FundamentalThresholds,
    MarketConditionRules,
    PaperTradingRules,
    PositionSizingRules,
    RiskManagementRules,
    ScoringRules,
    SignalThresholds,
    TechnicalThresholds,
    TradingRules,
    WatchlistManagementRules,
)


class TestRulesLoading:
    """Tests for rules loading and caching."""

    def test_rules_load_successfully(self) -> None:
        """Rules should load without errors."""
        rules = get_rules()
        assert isinstance(rules, TradingRules)
        assert rules.version is not None

    def test_rules_have_all_sections(self) -> None:
        """Rules should have all required sections."""
        rules = get_rules()

        # Check all 12 sections exist
        assert isinstance(rules.position_sizing, PositionSizingRules)
        assert isinstance(rules.risk_management, RiskManagementRules)
        assert isinstance(rules.technical_thresholds, TechnicalThresholds)
        assert isinstance(rules.scoring, ScoringRules)
        assert isinstance(rules.fundamentals, FundamentalThresholds)
        assert isinstance(rules.signals, SignalThresholds)
        assert isinstance(rules.fees, FeeRules)
        assert isinstance(rules.compliance, ComplianceRules)
        assert isinstance(rules.market, MarketConditionRules)
        assert isinstance(rules.paper_trading, PaperTradingRules)
        assert isinstance(rules.catalyst_impacts, dict)
        assert isinstance(rules.watchlist_management, WatchlistManagementRules)

    def test_rules_version_present(self) -> None:
        """Rules should have version metadata."""
        rules = get_rules()
        assert rules.version == "1.0.0"
        assert rules.updated == "2025-12-04"
        assert rules.updated_by == "Claude Code"

    def test_rules_caching(self) -> None:
        """Rules should be cached with 5-minute TTL."""
        # Force reload to reset cache
        rules1 = reload_rules()

        # Second call should return cached value
        rules2 = get_rules()
        assert rules1 is rules2  # Same object reference

        # Simulate cache expiration (mock time)
        import app.rules.loader as loader_module
        original_timestamp = loader_module._cache_timestamp
        loader_module._cache_timestamp = time.time() - (_CACHE_TTL_SECONDS + 1)

        # Should reload after expiration
        rules3 = get_rules()
        assert isinstance(rules3, TradingRules)

        # Restore timestamp
        loader_module._cache_timestamp = original_timestamp


class TestPositionSizingRules:
    """Tests for position sizing configuration."""

    def test_default_risk_percent_valid(self) -> None:
        """Default risk percent should be in valid range."""
        rules = get_rules()
        assert 0 < rules.position_sizing.default_risk_percent <= 0.10  # Max 10%
        assert rules.position_sizing.default_risk_percent == 0.015  # 1.5%

    def test_max_position_percent_reasonable(self) -> None:
        """Max position percent should not exceed 50%."""
        rules = get_rules()
        assert 0 < rules.position_sizing.max_position_percent <= 0.50
        assert rules.position_sizing.max_position_percent == 0.25  # 25%

    def test_kelly_fraction_bounds(self) -> None:
        """Kelly fraction should be between 0 and 1."""
        rules = get_rules()
        assert 0 < rules.position_sizing.default_kelly_fraction <= 1.0
        assert rules.position_sizing.default_kelly_fraction == 0.25  # Conservative

    def test_min_position_value_positive(self) -> None:
        """Minimum position value should be positive."""
        rules = get_rules()
        assert rules.position_sizing.min_position_value > 0
        assert rules.position_sizing.min_position_value == 100.0

    def test_risk_percent_bounds(self) -> None:
        """Risk percent bounds should be ordered correctly."""
        rules = get_rules()
        ps = rules.position_sizing
        assert ps.min_risk_percent < ps.default_risk_percent < ps.max_risk_percent


class TestRiskManagementRules:
    """Tests for risk management thresholds."""

    def test_drawdown_halt_threshold(self) -> None:
        """Drawdown halt should be at 25% per spec."""
        rules = get_rules()
        assert rules.risk_management.portfolio_drawdown_halt_pct == 25.0

    def test_max_single_trade_loss(self) -> None:
        """Max single trade loss should be 2% per spec."""
        rules = get_rules()
        assert rules.risk_management.max_single_trade_loss_pct == 2.0

    def test_warning_levels_ascending(self) -> None:
        """Warning levels should be in ascending order."""
        rules = get_rules()
        rm = rules.risk_management
        assert rm.drawdown_warning_level_1 < rm.drawdown_warning_level_2
        assert rm.drawdown_warning_level_2 < rm.portfolio_drawdown_halt_pct
        # Check specific values
        assert rm.drawdown_warning_level_1 == 10.0
        assert rm.drawdown_warning_level_2 == 15.0

    def test_exposure_limits_reasonable(self) -> None:
        """Exposure limits should be reasonable."""
        rules = get_rules()
        rm = rules.risk_management
        assert 0 < rm.default_position_limit <= 1.0
        assert 0 < rm.default_sector_limit <= 1.0
        assert rm.default_position_limit == 0.10  # 10%
        assert rm.default_sector_limit == 0.30  # 30%


class TestTechnicalThresholds:
    """Tests for technical indicator thresholds."""

    def test_rsi_bounds(self) -> None:
        """RSI values should be between 0 and 100."""
        rules = get_rules()
        tt = rules.technical_thresholds

        assert 0 <= tt.rsi_oversold <= 100
        assert 0 <= tt.rsi_overbought <= 100
        assert tt.rsi_oversold < tt.rsi_overbought
        assert tt.rsi_oversold == 30
        assert tt.rsi_overbought == 70

    def test_rsi_reversal_zones(self) -> None:
        """RSI reversal zones should be valid ranges."""
        rules = get_rules()
        tt = rules.technical_thresholds

        low_start, low_end = tt.rsi_reversal_zone_low
        high_start, high_end = tt.rsi_reversal_zone_high

        assert low_start < low_end
        assert high_start < high_end
        assert low_end <= high_start  # No overlap
        assert (low_start, low_end) == (30, 40)
        assert (high_start, high_end) == (60, 70)

    def test_macd_periods_valid(self) -> None:
        """MACD periods should be in correct order."""
        rules = get_rules()
        tt = rules.technical_thresholds

        assert tt.macd_fast < tt.macd_slow
        assert tt.macd_fast == 12
        assert tt.macd_slow == 26
        assert tt.macd_signal == 9

    def test_bollinger_settings(self) -> None:
        """Bollinger band settings should be valid."""
        rules = get_rules()
        tt = rules.technical_thresholds

        assert tt.bollinger_period > 0
        assert tt.bollinger_std_dev > 0
        assert tt.bollinger_period == 20
        assert tt.bollinger_std_dev == 2.0

    def test_bollinger_thresholds(self) -> None:
        """Bollinger thresholds should be in valid range."""
        rules = get_rules()
        tt = rules.technical_thresholds

        assert 0 <= tt.bollinger_lower_threshold <= 100
        assert 0 <= tt.bollinger_upper_threshold <= 100
        assert tt.bollinger_lower_threshold < tt.bollinger_upper_threshold

    def test_sma_periods_ascending(self) -> None:
        """SMA periods should be in ascending order."""
        rules = get_rules()
        sma_periods = rules.technical_thresholds.sma_periods

        assert len(sma_periods) > 0
        assert list(sma_periods) == sorted(sma_periods)
        assert sma_periods == (5, 20, 50, 200)

    def test_ema_periods_ascending(self) -> None:
        """EMA periods should be in ascending order."""
        rules = get_rules()
        ema_periods = rules.technical_thresholds.ema_periods

        assert len(ema_periods) > 0
        assert list(ema_periods) == sorted(ema_periods)
        assert ema_periods == (20, 50, 200)

    def test_atr_settings(self) -> None:
        """ATR settings should be valid."""
        rules = get_rules()
        tt = rules.technical_thresholds

        assert tt.atr_period > 0
        assert tt.stop_loss_atr_multiplier > 0
        assert tt.atr_period == 14
        assert tt.stop_loss_atr_multiplier == 2.0

    def test_stochastic_settings(self) -> None:
        """Stochastic oscillator settings should be valid."""
        rules = get_rules()
        tt = rules.technical_thresholds

        assert tt.stochastic_k_period > 0
        assert tt.stochastic_d_period > 0
        assert tt.stochastic_smooth_k > 0
        assert 0 <= tt.stochastic_oversold <= 100
        assert 0 <= tt.stochastic_overbought <= 100
        assert tt.stochastic_oversold < tt.stochastic_overbought


class TestScoringRules:
    """Tests for scoring system configuration."""

    def test_pillar_weights_sum_to_100(self) -> None:
        """Three pillar weights should sum to approximately 100."""
        rules = get_rules()
        total = (
            rules.scoring.price_weight
            + rules.scoring.technical_weight
            + rules.scoring.fundamental_weight
        )
        assert 99.0 <= total <= 101.0  # Allow small rounding

    def test_fundamental_weights_sum_to_1(self) -> None:
        """Fundamental sub-weights should sum to 1.0."""
        rules = get_rules()
        s = rules.scoring
        total = s.valuation_weight + s.growth_weight + s.health_weight + s.sentiment_weight
        assert 0.99 <= total <= 1.01  # Allow small rounding

    def test_staleness_ttl_positive(self) -> None:
        """Staleness TTL values should be positive."""
        rules = get_rules()
        assert rules.scoring.price_stale_ttl_minutes > 0
        assert rules.scoring.technical_stale_ttl_minutes > 0

    def test_signal_thresholds_reasonable(self) -> None:
        """Signal classification thresholds should be reasonable."""
        rules = get_rules()
        s = rules.scoring
        assert s.buy_confirmations_threshold > 0
        assert s.avoid_flags_threshold > 0
        assert s.signal_strength_divisor > 0


class TestFundamentalThresholds:
    """Tests for fundamental analysis thresholds."""

    def test_profit_margin_tiers_ascending(self) -> None:
        """Profit margin tiers should be in ascending order."""
        rules = get_rules()
        ft = rules.fundamentals
        assert ft.profit_margin_moderate < ft.profit_margin_good < ft.profit_margin_excellent

    def test_revenue_growth_tiers_ascending(self) -> None:
        """Revenue growth tiers should be in ascending order."""
        rules = get_rules()
        ft = rules.fundamentals
        assert (
            ft.revenue_growth_moderate
            < ft.revenue_growth_good
            < ft.revenue_growth_strong
            < ft.revenue_growth_exceptional
        )

    def test_debt_equity_tiers_ascending(self) -> None:
        """Debt-to-equity tiers should be in ascending order."""
        rules = get_rules()
        ft = rules.fundamentals
        assert ft.debt_equity_excellent < ft.debt_equity_good < ft.debt_equity_moderate

    def test_analyst_ratings_ordered(self) -> None:
        """Analyst ratings should be in order (1.0=Strong Buy, 5.0=Sell)."""
        rules = get_rules()
        ft = rules.fundamentals
        assert (
            ft.analyst_strong_buy
            < ft.analyst_buy
            < ft.analyst_hold
            < ft.analyst_neutral
            < ft.analyst_sell
        )


class TestSignalThresholds:
    """Tests for signal classification thresholds."""

    def test_news_sentiment_range(self) -> None:
        """News sentiment thresholds should be in valid range."""
        rules = get_rules()
        st = rules.signals
        assert -1.0 <= st.news_sentiment_negative < 0
        assert 0 < st.news_sentiment_positive <= 1.0

    def test_options_flow_range(self) -> None:
        """Options flow thresholds should be percentages (0-1)."""
        rules = get_rules()
        st = rules.signals
        assert 0 <= st.options_bearish <= 1.0
        assert 0 <= st.options_strong_bullish <= 1.0
        assert st.options_bearish < st.options_strong_bullish

    def test_options_tiers_ascending(self) -> None:
        """Options flow tiers should be in ascending order."""
        rules = get_rules()
        st = rules.signals
        assert (
            st.options_bearish
            < st.options_slight_bullish
            < st.options_moderate_bullish
            < st.options_strong_bullish
        )

    def test_earnings_days_positive(self) -> None:
        """Earnings-related day counts should be positive."""
        rules = get_rules()
        st = rules.signals
        assert st.earnings_avoid_days > 0
        assert st.earnings_event_days > 0

    def test_buy_thresholds_ordered(self) -> None:
        """Buy thresholds should be ordered correctly."""
        rules = get_rules()
        st = rules.signals
        assert st.buy_threshold < st.strong_buy_threshold


class TestCatalystImpacts:
    """Tests for catalyst impact configuration."""

    def test_all_events_have_impact(self) -> None:
        """All catalyst events should have an impact value."""
        rules = get_rules()
        catalysts = rules.catalyst_impacts

        assert len(catalysts) > 0
        for _event_type, catalyst in catalysts.items():
            assert isinstance(catalyst, CatalystImpact)
            assert catalyst.impact is not None
            # Impact should be a number (can be 0)
            assert isinstance(catalyst.impact, (int, float))

    def test_all_events_have_duration(self) -> None:
        """All catalyst events should have a duration_days value."""
        rules = get_rules()
        catalysts = rules.catalyst_impacts

        for _event_type, catalyst in catalysts.items():
            assert catalyst.duration_days > 0
            assert isinstance(catalyst.duration_days, int)

    def test_impact_range(self) -> None:
        """Impact values should be in expected range (-5 to +5)."""
        rules = get_rules()
        catalysts = rules.catalyst_impacts

        for event_type, catalyst in catalysts.items():
            assert -5.0 <= catalyst.impact <= 5.0, f"{event_type} impact out of range"

    def test_known_catalyst_events_present(self) -> None:
        """Known catalyst events should be present in config."""
        rules = get_rules()
        catalysts = rules.catalyst_impacts

        # Check for key events
        expected_events = [
            "earnings_beat",
            "earnings_miss",
            "guidance_raised",
            "guidance_lowered",
            "fda_approval",
            "fda_rejection",
            "analyst_upgrade",
            "analyst_downgrade",
            "insider_buy_large",
            "insider_sell_large",
        ]

        for event in expected_events:
            assert event in catalysts, f"Missing catalyst event: {event}"

    def test_positive_events_have_positive_impact(self) -> None:
        """Positive events should have positive impact."""
        rules = get_rules()
        c = rules.catalyst_impacts

        # Clearly positive events
        assert c["earnings_beat"].impact > 0
        assert c["guidance_raised"].impact > 0
        assert c["fda_approval"].impact > 0
        assert c["analyst_upgrade"].impact > 0
        assert c["insider_buy_large"].impact > 0

    def test_negative_events_have_negative_impact(self) -> None:
        """Negative events should have negative impact."""
        rules = get_rules()
        c = rules.catalyst_impacts

        # Clearly negative events
        assert c["earnings_miss"].impact < 0
        assert c["guidance_lowered"].impact < 0
        assert c["fda_rejection"].impact < 0
        assert c["analyst_downgrade"].impact < 0
        assert c["sec_investigation"].impact < 0


class TestFeeConfiguration:
    """Tests for fee and cost configuration."""

    def test_commission_not_zero(self) -> None:
        """Commission values should be positive (not zero-commission)."""
        rules = get_rules()
        fees = rules.fees

        assert fees.commission_per_share > 0
        assert fees.commission_per_trade > 0
        assert fees.commission_pct > 0
        assert fees.commission_minimum > 0

    def test_slippage_reasonable(self) -> None:
        """Slippage should be in reasonable range (0.01% to 1%)."""
        rules = get_rules()
        fees = rules.fees

        # Convert basis points to percentage
        slippage_pct = fees.slippage_bps / 100.0
        assert 0.01 <= slippage_pct <= 1.0  # 0.01% to 1%

    def test_institutional_fees_lower(self) -> None:
        """Institutional fees should be lower than retail."""
        rules = get_rules()
        fees = rules.fees

        assert fees.commission_per_share_institutional < fees.commission_per_share
        assert fees.commission_minimum_institutional < fees.commission_minimum
        assert fees.slippage_institutional_bps < fees.slippage_bps

    def test_stop_loss_and_targets_positive(self) -> None:
        """Stop loss and profit targets should be positive percentages."""
        rules = get_rules()
        fees = rules.fees

        assert fees.default_stop_loss_pct > 0
        assert fees.default_target_gain_pct > 0
        assert fees.momentum_target_profit_pct > 0
        assert fees.momentum_stop_loss_pct > 0

    def test_target_exceeds_stop_loss(self) -> None:
        """Profit targets should exceed stop loss (risk/reward ratio)."""
        rules = get_rules()
        fees = rules.fees

        assert fees.default_target_gain_pct > fees.default_stop_loss_pct
        assert fees.momentum_target_profit_pct > fees.momentum_stop_loss_pct


class TestComplianceRules:
    """Tests for compliance configuration."""

    def test_pdt_rules_valid(self) -> None:
        """PDT rules should match regulatory requirements."""
        rules = get_rules()
        compliance = rules.compliance

        assert compliance.pdt_day_trade_limit == 4  # FINRA regulation
        assert compliance.pdt_rolling_days == 5  # 5 business days
        assert compliance.pdt_equity_threshold == 25000.0  # $25k minimum

    def test_wash_sale_window(self) -> None:
        """Wash sale window should be 30 days per IRS rules."""
        rules = get_rules()
        assert rules.compliance.wash_sale_window_days == 30


class TestMarketConditionRules:
    """Tests for market condition thresholds."""

    def test_vix_levels_ascending(self) -> None:
        """VIX levels should be in ascending order."""
        rules = get_rules()
        mc = rules.market

        # Note: vix_normal and vix_elevated are both 20 in config
        assert mc.vix_low <= mc.vix_normal
        assert mc.vix_elevated <= mc.vix_high

    def test_treasury_thresholds(self) -> None:
        """Treasury yield thresholds should be reasonable."""
        rules = get_rules()
        mc = rules.market

        assert 0 < mc.treasury_10y_very_dovish < mc.treasury_10y_dovish
        assert mc.treasury_10y_dovish < mc.treasury_10y_hawkish
        assert mc.treasury_10y_hawkish < 10.0  # Sanity check

    def test_put_call_ratio_valid(self) -> None:
        """Put-call ratio threshold should be positive."""
        rules = get_rules()
        assert rules.market.put_call_bullish > 0

    def test_risk_free_rate_reasonable(self) -> None:
        """Default risk-free rate should be in reasonable range."""
        rules = get_rules()
        assert 0 <= rules.market.default_risk_free_rate <= 0.10  # 0-10%


class TestPaperTradingRules:
    """Tests for paper trading configuration."""

    def test_max_holding_days_positive(self) -> None:
        """Max holding days should be positive."""
        rules = get_rules()
        assert rules.paper_trading.max_holding_days > 0

    def test_default_position_pct_valid(self) -> None:
        """Default position percent should be in valid range."""
        rules = get_rules()
        assert 0 < rules.paper_trading.default_position_pct <= 1.0


class TestWatchlistManagementRules:
    """Tests for watchlist management configuration."""

    def test_size_limits_positive(self) -> None:
        """Watchlist size limits should be positive."""
        rules = get_rules()
        wm = rules.watchlist_management

        assert wm.max_watchlist_size > 0
        assert wm.max_daily_additions > 0
        assert wm.max_daily_removals > 0

    def test_discovery_thresholds_reasonable(self) -> None:
        """Discovery thresholds should be in reasonable ranges."""
        rules = get_rules()
        wm = rules.watchlist_management

        assert wm.discovery_score_threshold > 0
        assert wm.gainers_threshold_pct > 0
        assert wm.volume_spike_ratio > 1.0  # Spike = above normal
        assert wm.news_mention_threshold > 0

    def test_trimming_thresholds(self) -> None:
        """Trimming thresholds should be reasonable."""
        rules = get_rules()
        wm = rules.watchlist_management

        assert wm.min_days_watched > 0
        assert wm.min_score_threshold > 0
        assert isinstance(wm.auto_trim_enabled, bool)
        assert isinstance(wm.exclude_portfolio_holdings, bool)
