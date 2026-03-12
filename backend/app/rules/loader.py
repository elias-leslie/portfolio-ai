"""
Trading Rules Loader

Loads and caches trading rules from YAML configuration.
Supports hot reload via TTL-based cache invalidation.
"""

import time
from pathlib import Path
from typing import Any

import yaml

from app.logging_config import get_logger
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
    ThesisManagementRules,
    TradingRules,
    WatchlistManagementRules,
)

logger = get_logger(__name__)

# Cache settings
_CACHE_TTL_SECONDS = 300  # 5 minutes
_cached_rules: TradingRules | None = None
_cache_timestamp: float = 0.0

# Default rules path
_RULES_DIR = Path(__file__).parent.parent / "config" / "trading_rules"
_CURRENT_VERSION = "v1.0.0"


def _get_rules_path(version: str = _CURRENT_VERSION) -> Path:
    """Get path to rules YAML file for specified version."""
    return _RULES_DIR / version / "rules.yaml"


def _parse_list_to_tuple(data: Any, key: str) -> tuple[int, ...]:
    """Convert YAML list to tuple for frozen dataclass fields."""
    if key in data and isinstance(data[key], list):
        return tuple(data[key])
    return ()


def _load_position_sizing(data: dict[str, Any]) -> PositionSizingRules:
    """Parse position_sizing section."""
    section = data.get("position_sizing", {})
    return PositionSizingRules(
        default_risk_percent=section.get("default_risk_percent", 0.015),
        min_risk_percent=section.get("min_risk_percent", 0.005),
        max_risk_percent=section.get("max_risk_percent", 0.05),
        min_position_value=section.get("min_position_value", 100.0),
        max_position_percent=section.get("max_position_percent", 0.25),
        max_sector_exposure_pct=section.get("max_sector_exposure_pct", 0.20),
        default_kelly_fraction=section.get("default_kelly_fraction", 0.25),
        min_trades_for_kelly=section.get("min_trades_for_kelly", 30),
        min_position_percent=section.get("min_position_percent", 0.01),
        max_position_percent_adv=section.get("max_position_percent_adv", 0.01),
        min_volume_days=section.get("min_volume_days", 20),
    )


def _load_risk_management(data: dict[str, Any]) -> RiskManagementRules:
    """Parse risk_management section."""
    section = data.get("risk_management", {})
    return RiskManagementRules(
        portfolio_drawdown_halt_pct=section.get("portfolio_drawdown_halt_pct", 25.0),
        drawdown_warning_level_1=section.get("drawdown_warning_level_1", 10.0),
        drawdown_warning_level_2=section.get("drawdown_warning_level_2", 15.0),
        max_single_trade_loss_pct=section.get("max_single_trade_loss_pct", 2.0),
        default_position_limit=section.get("default_position_limit", 0.10),
        default_sector_limit=section.get("default_sector_limit", 0.30),
        warning_threshold_pct=section.get("warning_threshold_pct", 0.80),
    )


def _load_technical_thresholds(data: dict[str, Any]) -> TechnicalThresholds:
    """Parse technical_thresholds section."""
    section = data.get("technical_thresholds", {})

    # Handle list-to-tuple conversions
    rsi_low = section.get("rsi_reversal_zone_low", [30, 40])
    rsi_high = section.get("rsi_reversal_zone_high", [60, 70])
    sma = section.get("sma_periods", [5, 20, 50, 200])
    ema = section.get("ema_periods", [20, 50, 200])

    return TechnicalThresholds(
        rsi_period=section.get("rsi_period", 14),
        rsi_oversold=section.get("rsi_oversold", 30),
        rsi_overbought=section.get("rsi_overbought", 70),
        rsi_reversal_zone_low=(rsi_low[0], rsi_low[1]) if len(rsi_low) >= 2 else (30, 40),
        rsi_reversal_zone_high=(rsi_high[0], rsi_high[1]) if len(rsi_high) >= 2 else (60, 70),
        sma_periods=tuple(sma),
        ema_periods=tuple(ema),
        macd_fast=section.get("macd_fast", 12),
        macd_slow=section.get("macd_slow", 26),
        macd_signal=section.get("macd_signal", 9),
        bollinger_period=section.get("bollinger_period", 20),
        bollinger_std_dev=section.get("bollinger_std_dev", 2.0),
        bollinger_lower_threshold=section.get("bollinger_lower_threshold", 20),
        bollinger_upper_threshold=section.get("bollinger_upper_threshold", 80),
        atr_period=section.get("atr_period", 14),
        stop_loss_atr_multiplier=section.get("stop_loss_atr_multiplier", 2.0),
        stochastic_k_period=section.get("stochastic_k_period", 14),
        stochastic_d_period=section.get("stochastic_d_period", 3),
        stochastic_smooth_k=section.get("stochastic_smooth_k", 3),
        stochastic_oversold=section.get("stochastic_oversold", 20),
        stochastic_overbought=section.get("stochastic_overbought", 80),
        volume_sma_period=section.get("volume_sma_period", 20),
        volume_threshold_ratio=section.get("volume_threshold_ratio", 0.7),
        volume_high_threshold=section.get("volume_high_threshold", 1.5),
        trend_threshold_pct=section.get("trend_threshold_pct", 0.02),
        lookback_days=section.get("lookback_days", 250),
        min_days_for_sma200=section.get("min_days_for_sma200", 200),
    )


def _load_scoring(data: dict[str, Any]) -> ScoringRules:
    """Parse scoring section."""
    section = data.get("scoring", {})
    return ScoringRules(
        price_weight=section.get("price_weight", 33.0),
        technical_weight=section.get("technical_weight", 33.0),
        fundamental_weight=section.get("fundamental_weight", 34.0),
        valuation_weight=section.get("valuation_weight", 0.25),
        growth_weight=section.get("growth_weight", 0.35),
        health_weight=section.get("health_weight", 0.25),
        sentiment_weight=section.get("sentiment_weight", 0.15),
        price_stale_ttl_minutes=section.get("price_stale_ttl_minutes", 15),
        technical_stale_ttl_minutes=section.get("technical_stale_ttl_minutes", 60),
        buy_confirmations_threshold=section.get("buy_confirmations_threshold", 10),
        avoid_flags_threshold=section.get("avoid_flags_threshold", 2),
        signal_strength_divisor=section.get("signal_strength_divisor", 2.4),
    )


def _load_fundamentals(data: dict[str, Any]) -> FundamentalThresholds:
    """Parse fundamentals section."""
    section = data.get("fundamentals", {})
    return FundamentalThresholds(
        profit_margin_excellent=section.get("profit_margin_excellent", 0.20),
        profit_margin_good=section.get("profit_margin_good", 0.10),
        profit_margin_moderate=section.get("profit_margin_moderate", 0.05),
        revenue_growth_exceptional=section.get("revenue_growth_exceptional", 0.30),
        revenue_growth_strong=section.get("revenue_growth_strong", 0.20),
        revenue_growth_good=section.get("revenue_growth_good", 0.10),
        revenue_growth_moderate=section.get("revenue_growth_moderate", 0.05),
        debt_equity_excellent=section.get("debt_equity_excellent", 0.3),
        debt_equity_good=section.get("debt_equity_good", 0.7),
        debt_equity_moderate=section.get("debt_equity_moderate", 1.5),
        debt_equity_high=section.get("debt_equity_high", 2.5),
        debt_equity_weak=section.get("debt_equity_weak", 2.0),
        analyst_strong_buy=section.get("analyst_strong_buy", 1.5),
        analyst_buy=section.get("analyst_buy", 2.0),
        analyst_hold=section.get("analyst_hold", 2.5),
        analyst_neutral=section.get("analyst_neutral", 3.5),
        analyst_sell=section.get("analyst_sell", 4.5),
        analyst_buy_pct_strong=section.get("analyst_buy_pct_strong", 0.70),
        analyst_buy_pct_moderate=section.get("analyst_buy_pct_moderate", 0.50),
    )


def _load_signals(data: dict[str, Any]) -> SignalThresholds:
    """Parse signals section."""
    section = data.get("signals", {})
    return SignalThresholds(
        news_sentiment_positive=section.get("news_sentiment_positive", 0.2),
        news_sentiment_negative=section.get("news_sentiment_negative", -0.3),
        options_strong_bullish=section.get("options_strong_bullish", 0.58),
        options_moderate_bullish=section.get("options_moderate_bullish", 0.55),
        options_slight_bullish=section.get("options_slight_bullish", 0.52),
        options_bearish=section.get("options_bearish", 0.45),
        earnings_avoid_days=section.get("earnings_avoid_days", 5),
        earnings_event_days=section.get("earnings_event_days", 7),
        strong_buy_threshold=section.get("strong_buy_threshold", 8),
        buy_threshold=section.get("buy_threshold", 6),
    )


def _load_fees(data: dict[str, Any]) -> FeeRules:
    """Parse fees section."""
    section = data.get("fees", {})
    return FeeRules(
        slippage_bps=section.get("slippage_bps", 5.0),
        slippage_dynamic_factor=section.get("slippage_dynamic_factor", 0.1),
        slippage_institutional_bps=section.get("slippage_institutional_bps", 2.0),
        commission_per_share=section.get("commission_per_share", 0.005),
        commission_per_trade=section.get("commission_per_trade", 1.00),
        commission_pct=section.get("commission_pct", 0.001),
        commission_minimum=section.get("commission_minimum", 1.00),
        commission_per_share_institutional=section.get("commission_per_share_institutional", 0.001),
        commission_minimum_institutional=section.get("commission_minimum_institutional", 0.50),
        default_stop_loss_pct=section.get("default_stop_loss_pct", 8.0),
        default_target_gain_pct=section.get("default_target_gain_pct", 15.0),
        momentum_target_profit_pct=section.get("momentum_target_profit_pct", 20.0),
        momentum_stop_loss_pct=section.get("momentum_stop_loss_pct", 8.0),
    )


def _load_compliance(data: dict[str, Any]) -> ComplianceRules:
    """Parse compliance section."""
    section = data.get("compliance", {})
    return ComplianceRules(
        pdt_day_trade_limit=section.get("pdt_day_trade_limit", 4),
        pdt_rolling_days=section.get("pdt_rolling_days", 5),
        pdt_equity_threshold=section.get("pdt_equity_threshold", 25000.0),
        wash_sale_window_days=section.get("wash_sale_window_days", 30),
    )


def _load_market(data: dict[str, Any]) -> MarketConditionRules:
    """Parse market section."""
    section = data.get("market", {})
    return MarketConditionRules(
        vix_low=section.get("vix_low", 15),
        vix_normal=section.get("vix_normal", 20),
        vix_elevated=section.get("vix_elevated", 20),
        vix_high=section.get("vix_high", 30),
        treasury_10y_dovish=section.get("treasury_10y_dovish", 3.5),
        treasury_10y_hawkish=section.get("treasury_10y_hawkish", 4.5),
        treasury_10y_very_dovish=section.get("treasury_10y_very_dovish", 3.0),
        put_call_bullish=section.get("put_call_bullish", 0.7),
        default_risk_free_rate=section.get("default_risk_free_rate", 0.04),
    )


def _load_paper_trading(data: dict[str, Any]) -> PaperTradingRules:
    """Parse paper_trading section."""
    section = data.get("paper_trading", {})
    return PaperTradingRules(
        max_holding_days=section.get("max_holding_days", 60),
        default_position_pct=section.get("default_position_pct", 0.05),
    )


def _load_catalyst_impacts(data: dict[str, Any]) -> dict[str, CatalystImpact]:
    """Parse catalyst_impacts section."""
    section = data.get("catalyst_impacts", {})
    result: dict[str, CatalystImpact] = {}
    for event_type, config in section.items():
        if isinstance(config, dict):
            result[event_type] = CatalystImpact(
                impact=config.get("impact", 0.0),
                duration_days=config.get("duration_days", 3),
            )
    return result


def _load_watchlist_management(data: dict[str, Any]) -> WatchlistManagementRules:
    """Parse watchlist_management section."""
    section = data.get("watchlist_management", {})
    return WatchlistManagementRules(
        max_watchlist_size=section.get("max_watchlist_size", 50),
        max_daily_additions=section.get("max_daily_additions", 5),
        max_daily_removals=section.get("max_daily_removals", 3),
        discovery_score_threshold=section.get("discovery_score_threshold", 6.0),
        gainers_threshold_pct=section.get("gainers_threshold_pct", 5.0),
        volume_spike_ratio=section.get("volume_spike_ratio", 2.0),
        news_mention_threshold=section.get("news_mention_threshold", 3),
        auto_trim_enabled=section.get("auto_trim_enabled", True),
        min_days_watched=section.get("min_days_watched", 7),
        min_score_threshold=section.get("min_score_threshold", 4.0),
        exclude_portfolio_holdings=section.get("exclude_portfolio_holdings", True),
    )


def _load_thesis_management(data: dict[str, Any]) -> ThesisManagementRules:
    """Parse thesis_management section."""
    section = data.get("thesis_management", {})
    return ThesisManagementRules(
        thesis_generation_enabled=section.get("thesis_generation_enabled", True),
        thesis_cache_ttl_hours=section.get("thesis_cache_ttl_hours", 24),
        cross_validation_enabled=section.get("cross_validation_enabled", True),
        min_cross_validation_score=section.get("min_cross_validation_score", 0.5),
        auto_flag_low_confidence=section.get("auto_flag_low_confidence", True),
        auto_remove_on_invalidation=section.get("auto_remove_on_invalidation", True),
        version_retention_days=section.get("version_retention_days", 365),
        max_versions_per_symbol=section.get("max_versions_per_symbol", 50),
        max_generations_per_day=section.get("max_generations_per_day", 10),
        generation_cooldown_seconds=section.get("generation_cooldown_seconds", 60),
    )


def _load_rules_from_yaml(path: Path) -> TradingRules:
    """Load and parse trading rules from YAML file."""
    if not path.exists():
        logger.warning("rules_file_not_found", path=str(path))
        return TradingRules()

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        logger.warning("rules_file_empty", path=str(path))
        return TradingRules()

    return TradingRules(
        version=data.get("version", "1.0.0"),
        updated=data.get("updated", ""),
        updated_by=data.get("updated_by", ""),
        position_sizing=_load_position_sizing(data),
        risk_management=_load_risk_management(data),
        technical_thresholds=_load_technical_thresholds(data),
        scoring=_load_scoring(data),
        fundamentals=_load_fundamentals(data),
        signals=_load_signals(data),
        fees=_load_fees(data),
        compliance=_load_compliance(data),
        market=_load_market(data),
        paper_trading=_load_paper_trading(data),
        catalyst_impacts=_load_catalyst_impacts(data),
        watchlist_management=_load_watchlist_management(data),
        thesis_management=_load_thesis_management(data),
    )


def get_rules(version: str = _CURRENT_VERSION) -> TradingRules:
    """Get trading rules, using cache if available and not expired.

    Args:
        version: Rules version to load (default: current version)

    Returns:
        TradingRules dataclass with all configuration values
    """
    global _cached_rules, _cache_timestamp  # noqa: PLW0603

    now = time.time()

    # Check cache validity
    if _cached_rules is not None and (now - _cache_timestamp) < _CACHE_TTL_SECONDS:
        return _cached_rules

    # Load from YAML
    path = _get_rules_path(version)
    logger.info("loading_trading_rules", path=str(path))

    _cached_rules = _load_rules_from_yaml(path)
    _cache_timestamp = now

    logger.info("trading_rules_loaded", version=_cached_rules.version)
    return _cached_rules


def reload_rules(version: str = _CURRENT_VERSION) -> TradingRules:
    """Force reload of trading rules, bypassing cache.

    Args:
        version: Rules version to load

    Returns:
        Freshly loaded TradingRules
    """
    global _cached_rules, _cache_timestamp  # noqa: PLW0603

    path = _get_rules_path(version)
    logger.info("force_reloading_trading_rules", path=str(path))

    _cached_rules = _load_rules_from_yaml(path)
    _cache_timestamp = time.time()

    return _cached_rules
