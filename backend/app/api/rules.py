"""
Trading Rules API Endpoints

GET /api/rules - Returns all trading rules from rules.yaml
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.rules.loader import get_rules

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/rules")
def get_trading_rules() -> dict[str, Any]:
    """
    Get all trading rules from rules.yaml configuration.

    Returns:
        dict: Complete trading rules configuration including:
            - version: Rules version
            - updated: Last update date
            - updated_by: Last updated by
            - position_sizing: Position sizing rules
            - risk_management: Risk management rules
            - technical_thresholds: Technical indicator thresholds
            - scoring: Scoring weights and thresholds
            - fundamentals: Fundamental analysis thresholds
            - signals: Signal generation thresholds
            - fees: Fee and cost calculations
            - compliance: Regulatory compliance rules
            - market: Market condition thresholds
            - paper_trading: Paper trading configuration
            - catalyst_impacts: Event impact scoring
            - watchlist_management: Watchlist automation rules
    """
    try:
        rules = get_rules()

        # Convert to dict for JSON serialization
        # Use dataclass fields directly
        return {
            "version": rules.version,
            "updated": rules.updated,
            "updated_by": rules.updated_by,
            "position_sizing": {
                "default_risk_percent": rules.position_sizing.default_risk_percent,
                "min_risk_percent": rules.position_sizing.min_risk_percent,
                "max_risk_percent": rules.position_sizing.max_risk_percent,
                "min_position_value": rules.position_sizing.min_position_value,
                "max_position_percent": rules.position_sizing.max_position_percent,
                "max_sector_exposure_pct": rules.position_sizing.max_sector_exposure_pct,
                "default_kelly_fraction": rules.position_sizing.default_kelly_fraction,
                "min_trades_for_kelly": rules.position_sizing.min_trades_for_kelly,
                "min_position_percent": rules.position_sizing.min_position_percent,
                "max_position_percent_adv": rules.position_sizing.max_position_percent_adv,
                "min_volume_days": rules.position_sizing.min_volume_days,
            },
            "risk_management": {
                "portfolio_drawdown_halt_pct": rules.risk_management.portfolio_drawdown_halt_pct,
                "drawdown_warning_level_1": rules.risk_management.drawdown_warning_level_1,
                "drawdown_warning_level_2": rules.risk_management.drawdown_warning_level_2,
                "max_single_trade_loss_pct": rules.risk_management.max_single_trade_loss_pct,
                "default_position_limit": rules.risk_management.default_position_limit,
                "default_sector_limit": rules.risk_management.default_sector_limit,
                "warning_threshold_pct": rules.risk_management.warning_threshold_pct,
            },
            "technical_thresholds": {
                "rsi_period": rules.technical_thresholds.rsi_period,
                "rsi_oversold": rules.technical_thresholds.rsi_oversold,
                "rsi_overbought": rules.technical_thresholds.rsi_overbought,
                "rsi_reversal_zone_low": list(rules.technical_thresholds.rsi_reversal_zone_low),
                "rsi_reversal_zone_high": list(rules.technical_thresholds.rsi_reversal_zone_high),
                "sma_periods": list(rules.technical_thresholds.sma_periods),
                "ema_periods": list(rules.technical_thresholds.ema_periods),
                "macd_fast": rules.technical_thresholds.macd_fast,
                "macd_slow": rules.technical_thresholds.macd_slow,
                "macd_signal": rules.technical_thresholds.macd_signal,
                "bollinger_period": rules.technical_thresholds.bollinger_period,
                "bollinger_std_dev": rules.technical_thresholds.bollinger_std_dev,
                "bollinger_lower_threshold": rules.technical_thresholds.bollinger_lower_threshold,
                "bollinger_upper_threshold": rules.technical_thresholds.bollinger_upper_threshold,
                "atr_period": rules.technical_thresholds.atr_period,
                "stop_loss_atr_multiplier": rules.technical_thresholds.stop_loss_atr_multiplier,
                "stochastic_k_period": rules.technical_thresholds.stochastic_k_period,
                "stochastic_d_period": rules.technical_thresholds.stochastic_d_period,
                "stochastic_smooth_k": rules.technical_thresholds.stochastic_smooth_k,
                "stochastic_oversold": rules.technical_thresholds.stochastic_oversold,
                "stochastic_overbought": rules.technical_thresholds.stochastic_overbought,
                "volume_sma_period": rules.technical_thresholds.volume_sma_period,
                "volume_threshold_ratio": rules.technical_thresholds.volume_threshold_ratio,
                "volume_high_threshold": rules.technical_thresholds.volume_high_threshold,
                "trend_threshold_pct": rules.technical_thresholds.trend_threshold_pct,
                "lookback_days": rules.technical_thresholds.lookback_days,
                "min_days_for_sma200": rules.technical_thresholds.min_days_for_sma200,
            },
            "scoring": {
                "price_weight": rules.scoring.price_weight,
                "technical_weight": rules.scoring.technical_weight,
                "fundamental_weight": rules.scoring.fundamental_weight,
                "valuation_weight": rules.scoring.valuation_weight,
                "growth_weight": rules.scoring.growth_weight,
                "health_weight": rules.scoring.health_weight,
                "sentiment_weight": rules.scoring.sentiment_weight,
                "price_stale_ttl_minutes": rules.scoring.price_stale_ttl_minutes,
                "technical_stale_ttl_minutes": rules.scoring.technical_stale_ttl_minutes,
                "buy_confirmations_threshold": rules.scoring.buy_confirmations_threshold,
                "avoid_flags_threshold": rules.scoring.avoid_flags_threshold,
                "signal_strength_divisor": rules.scoring.signal_strength_divisor,
            },
            "fundamentals": {
                "profit_margin_excellent": rules.fundamentals.profit_margin_excellent,
                "profit_margin_good": rules.fundamentals.profit_margin_good,
                "profit_margin_moderate": rules.fundamentals.profit_margin_moderate,
                "revenue_growth_exceptional": rules.fundamentals.revenue_growth_exceptional,
                "revenue_growth_strong": rules.fundamentals.revenue_growth_strong,
                "revenue_growth_good": rules.fundamentals.revenue_growth_good,
                "revenue_growth_moderate": rules.fundamentals.revenue_growth_moderate,
                "debt_equity_excellent": rules.fundamentals.debt_equity_excellent,
                "debt_equity_good": rules.fundamentals.debt_equity_good,
                "debt_equity_moderate": rules.fundamentals.debt_equity_moderate,
                "debt_equity_high": rules.fundamentals.debt_equity_high,
                "debt_equity_weak": rules.fundamentals.debt_equity_weak,
                "analyst_strong_buy": rules.fundamentals.analyst_strong_buy,
                "analyst_buy": rules.fundamentals.analyst_buy,
                "analyst_hold": rules.fundamentals.analyst_hold,
                "analyst_neutral": rules.fundamentals.analyst_neutral,
                "analyst_sell": rules.fundamentals.analyst_sell,
                "analyst_buy_pct_strong": rules.fundamentals.analyst_buy_pct_strong,
                "analyst_buy_pct_moderate": rules.fundamentals.analyst_buy_pct_moderate,
            },
            "signals": {
                "news_sentiment_positive": rules.signals.news_sentiment_positive,
                "news_sentiment_negative": rules.signals.news_sentiment_negative,
                "options_strong_bullish": rules.signals.options_strong_bullish,
                "options_moderate_bullish": rules.signals.options_moderate_bullish,
                "options_slight_bullish": rules.signals.options_slight_bullish,
                "options_bearish": rules.signals.options_bearish,
                "earnings_avoid_days": rules.signals.earnings_avoid_days,
                "earnings_event_days": rules.signals.earnings_event_days,
                "strong_buy_threshold": rules.signals.strong_buy_threshold,
                "buy_threshold": rules.signals.buy_threshold,
            },
            "fees": {
                "slippage_bps": rules.fees.slippage_bps,
                "slippage_dynamic_factor": rules.fees.slippage_dynamic_factor,
                "slippage_institutional_bps": rules.fees.slippage_institutional_bps,
                "commission_per_share": rules.fees.commission_per_share,
                "commission_per_trade": rules.fees.commission_per_trade,
                "commission_pct": rules.fees.commission_pct,
                "commission_minimum": rules.fees.commission_minimum,
                "commission_per_share_institutional": rules.fees.commission_per_share_institutional,
                "commission_minimum_institutional": rules.fees.commission_minimum_institutional,
                "default_stop_loss_pct": rules.fees.default_stop_loss_pct,
                "default_target_gain_pct": rules.fees.default_target_gain_pct,
                "momentum_target_profit_pct": rules.fees.momentum_target_profit_pct,
                "momentum_stop_loss_pct": rules.fees.momentum_stop_loss_pct,
            },
            "compliance": {
                "pdt_day_trade_limit": rules.compliance.pdt_day_trade_limit,
                "pdt_rolling_days": rules.compliance.pdt_rolling_days,
                "pdt_equity_threshold": rules.compliance.pdt_equity_threshold,
                "wash_sale_window_days": rules.compliance.wash_sale_window_days,
            },
            "market": {
                "vix_low": rules.market.vix_low,
                "vix_normal": rules.market.vix_normal,
                "vix_elevated": rules.market.vix_elevated,
                "vix_high": rules.market.vix_high,
                "treasury_10y_dovish": rules.market.treasury_10y_dovish,
                "treasury_10y_hawkish": rules.market.treasury_10y_hawkish,
                "treasury_10y_very_dovish": rules.market.treasury_10y_very_dovish,
                "put_call_bullish": rules.market.put_call_bullish,
                "default_risk_free_rate": rules.market.default_risk_free_rate,
            },
            "paper_trading": {
                "max_holding_days": rules.paper_trading.max_holding_days,
                "default_position_pct": rules.paper_trading.default_position_pct,
            },
            "catalyst_impacts": {
                event_type: {
                    "impact": catalyst.impact,
                    "duration_days": catalyst.duration_days,
                }
                for event_type, catalyst in rules.catalyst_impacts.items()
            },
            "watchlist_management": {
                "max_watchlist_size": rules.watchlist_management.max_watchlist_size,
                "max_daily_additions": rules.watchlist_management.max_daily_additions,
                "max_daily_removals": rules.watchlist_management.max_daily_removals,
                "discovery_score_threshold": rules.watchlist_management.discovery_score_threshold,
                "gainers_threshold_pct": rules.watchlist_management.gainers_threshold_pct,
                "volume_spike_ratio": rules.watchlist_management.volume_spike_ratio,
                "news_mention_threshold": rules.watchlist_management.news_mention_threshold,
                "auto_trim_enabled": rules.watchlist_management.auto_trim_enabled,
                "min_days_watched": rules.watchlist_management.min_days_watched,
                "min_score_threshold": rules.watchlist_management.min_score_threshold,
                "exclude_portfolio_holdings": rules.watchlist_management.exclude_portfolio_holdings,
            },
        }
    except Exception as e:
        logger.error(f"Failed to load trading rules: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load trading rules: {str(e)}")
