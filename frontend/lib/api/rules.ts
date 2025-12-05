/**
 * Trading Rules API Client
 */

import { get } from "./client";

export interface CatalystImpact {
  impact: number;
  duration_days: number;
}

export interface TradingRules {
  version: string;
  updated: string;
  updated_by: string;
  position_sizing: {
    default_risk_percent: number;
    min_risk_percent: number;
    max_risk_percent: number;
    min_position_value: number;
    max_position_percent: number;
    max_sector_exposure_pct: number;
    default_kelly_fraction: number;
    min_trades_for_kelly: number;
    min_position_percent: number;
    max_position_percent_adv: number;
    min_volume_days: number;
  };
  risk_management: {
    portfolio_drawdown_halt_pct: number;
    drawdown_warning_level_1: number;
    drawdown_warning_level_2: number;
    max_single_trade_loss_pct: number;
    default_position_limit: number;
    default_sector_limit: number;
    warning_threshold_pct: number;
  };
  technical_thresholds: {
    rsi_period: number;
    rsi_oversold: number;
    rsi_overbought: number;
    rsi_reversal_zone_low: [number, number];
    rsi_reversal_zone_high: [number, number];
    sma_periods: number[];
    ema_periods: number[];
    macd_fast: number;
    macd_slow: number;
    macd_signal: number;
    bollinger_period: number;
    bollinger_std_dev: number;
    bollinger_lower_threshold: number;
    bollinger_upper_threshold: number;
    atr_period: number;
    stop_loss_atr_multiplier: number;
    stochastic_k_period: number;
    stochastic_d_period: number;
    stochastic_smooth_k: number;
    stochastic_oversold: number;
    stochastic_overbought: number;
    volume_sma_period: number;
    volume_threshold_ratio: number;
    volume_high_threshold: number;
    trend_threshold_pct: number;
    lookback_days: number;
    min_days_for_sma200: number;
  };
  scoring: {
    price_weight: number;
    technical_weight: number;
    fundamental_weight: number;
    valuation_weight: number;
    growth_weight: number;
    health_weight: number;
    sentiment_weight: number;
    price_stale_ttl_minutes: number;
    technical_stale_ttl_minutes: number;
    buy_confirmations_threshold: number;
    avoid_flags_threshold: number;
    signal_strength_divisor: number;
  };
  fundamentals: {
    profit_margin_excellent: number;
    profit_margin_good: number;
    profit_margin_moderate: number;
    revenue_growth_exceptional: number;
    revenue_growth_strong: number;
    revenue_growth_good: number;
    revenue_growth_moderate: number;
    debt_equity_excellent: number;
    debt_equity_good: number;
    debt_equity_moderate: number;
    debt_equity_high: number;
    debt_equity_weak: number;
    analyst_strong_buy: number;
    analyst_buy: number;
    analyst_hold: number;
    analyst_neutral: number;
    analyst_sell: number;
    analyst_buy_pct_strong: number;
    analyst_buy_pct_moderate: number;
  };
  signals: {
    news_sentiment_positive: number;
    news_sentiment_negative: number;
    options_strong_bullish: number;
    options_moderate_bullish: number;
    options_slight_bullish: number;
    options_bearish: number;
    earnings_avoid_days: number;
    earnings_event_days: number;
    strong_buy_threshold: number;
    buy_threshold: number;
  };
  fees: {
    slippage_bps: number;
    slippage_dynamic_factor: number;
    slippage_institutional_bps: number;
    commission_per_share: number;
    commission_per_trade: number;
    commission_pct: number;
    commission_minimum: number;
    commission_per_share_institutional: number;
    commission_minimum_institutional: number;
    default_stop_loss_pct: number;
    default_target_gain_pct: number;
    momentum_target_profit_pct: number;
    momentum_stop_loss_pct: number;
  };
  compliance: {
    pdt_day_trade_limit: number;
    pdt_rolling_days: number;
    pdt_equity_threshold: number;
    wash_sale_window_days: number;
  };
  market: {
    vix_low: number;
    vix_normal: number;
    vix_elevated: number;
    vix_high: number;
    treasury_10y_dovish: number;
    treasury_10y_hawkish: number;
    treasury_10y_very_dovish: number;
    put_call_bullish: number;
    default_risk_free_rate: number;
  };
  paper_trading: {
    max_holding_days: number;
    default_position_pct: number;
  };
  catalyst_impacts: Record<string, CatalystImpact>;
  watchlist_management: {
    max_watchlist_size: number;
    max_daily_additions: number;
    max_daily_removals: number;
    discovery_score_threshold: number;
    gainers_threshold_pct: number;
    volume_spike_ratio: number;
    news_mention_threshold: number;
    auto_trim_enabled: boolean;
    min_days_watched: number;
    min_score_threshold: number;
    exclude_portfolio_holdings: boolean;
  };
}

export async function fetchRules(): Promise<TradingRules> {
  return get<TradingRules>("/api/rules");
}
