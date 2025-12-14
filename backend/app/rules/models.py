"""
Trading Rules Data Models

Typed dataclass models for trading rules configuration.
Provides IDE autocomplete and type safety.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PositionSizingRules:
    """Position sizing parameters."""

    # Risk per trade
    default_risk_percent: float = 0.015
    min_risk_percent: float = 0.005
    max_risk_percent: float = 0.05

    # Position limits
    min_position_value: float = 100.0
    max_position_percent: float = 0.25
    max_sector_exposure_pct: float = 0.20

    # Kelly criterion
    default_kelly_fraction: float = 0.25
    min_trades_for_kelly: int = 30
    min_position_percent: float = 0.01

    # Liquidity
    max_position_percent_adv: float = 0.01
    min_volume_days: int = 20


@dataclass(frozen=True)
class RiskManagementRules:
    """Risk management thresholds."""

    # Drawdown thresholds
    portfolio_drawdown_halt_pct: float = 25.0
    drawdown_warning_level_1: float = 10.0
    drawdown_warning_level_2: float = 15.0

    # Per-trade limits
    max_single_trade_loss_pct: float = 2.0

    # Exposure budgets
    default_position_limit: float = 0.10
    default_sector_limit: float = 0.30
    warning_threshold_pct: float = 0.80


@dataclass(frozen=True)
class TechnicalThresholds:
    """Technical indicator thresholds."""

    # RSI
    rsi_period: int = 14
    rsi_oversold: int = 30
    rsi_overbought: int = 70
    rsi_reversal_zone_low: tuple[int, int] = (30, 40)
    rsi_reversal_zone_high: tuple[int, int] = (60, 70)

    # Moving averages
    sma_periods: tuple[int, ...] = (5, 20, 50, 200)
    ema_periods: tuple[int, ...] = (20, 50, 200)

    # MACD
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Bollinger Bands
    bollinger_period: int = 20
    bollinger_std_dev: float = 2.0
    bollinger_lower_threshold: int = 20
    bollinger_upper_threshold: int = 80

    # ATR
    atr_period: int = 14
    stop_loss_atr_multiplier: float = 2.0

    # Stochastic
    stochastic_k_period: int = 14
    stochastic_d_period: int = 3
    stochastic_smooth_k: int = 3
    stochastic_oversold: int = 20
    stochastic_overbought: int = 80

    # Volume
    volume_sma_period: int = 20
    volume_threshold_ratio: float = 0.7
    volume_high_threshold: float = 1.5

    # Trend
    trend_threshold_pct: float = 0.02
    lookback_days: int = 250
    min_days_for_sma200: int = 200


@dataclass(frozen=True)
class ScoringRules:
    """Scoring system weights and thresholds."""

    # 3-pillar weights
    price_weight: float = 33.0
    technical_weight: float = 33.0
    fundamental_weight: float = 34.0

    # Fundamental pillar weights
    valuation_weight: float = 0.25
    growth_weight: float = 0.35
    health_weight: float = 0.25
    sentiment_weight: float = 0.15

    # Staleness TTL
    price_stale_ttl_minutes: int = 15
    technical_stale_ttl_minutes: int = 60

    # Signal classification
    buy_confirmations_threshold: int = 10
    avoid_flags_threshold: int = 2
    signal_strength_divisor: float = 2.4


@dataclass(frozen=True)
class FundamentalThresholds:
    """Fundamental analysis thresholds."""

    # Profit margin
    profit_margin_excellent: float = 0.20
    profit_margin_good: float = 0.10
    profit_margin_moderate: float = 0.05

    # Revenue growth
    revenue_growth_exceptional: float = 0.30
    revenue_growth_strong: float = 0.20
    revenue_growth_good: float = 0.10
    revenue_growth_moderate: float = 0.05

    # Debt-to-equity
    debt_equity_excellent: float = 0.3
    debt_equity_good: float = 0.7
    debt_equity_moderate: float = 1.5
    debt_equity_high: float = 2.5
    debt_equity_weak: float = 2.0

    # Analyst recommendations
    analyst_strong_buy: float = 1.5
    analyst_buy: float = 2.0
    analyst_hold: float = 2.5
    analyst_neutral: float = 3.5
    analyst_sell: float = 4.5
    analyst_buy_pct_strong: float = 0.70
    analyst_buy_pct_moderate: float = 0.50


@dataclass(frozen=True)
class SignalThresholds:
    """Signal classification thresholds."""

    # News sentiment
    news_sentiment_positive: float = 0.2
    news_sentiment_negative: float = -0.3

    # Options flow
    options_strong_bullish: float = 0.58
    options_moderate_bullish: float = 0.55
    options_slight_bullish: float = 0.52
    options_bearish: float = 0.45

    # Earnings
    earnings_avoid_days: int = 5
    earnings_event_days: int = 7

    # Signal strength
    strong_buy_threshold: int = 8
    buy_threshold: int = 6


@dataclass(frozen=True)
class FeeRules:
    """Trading cost configuration."""

    # Slippage
    slippage_bps: float = 5.0
    slippage_dynamic_factor: float = 0.1
    slippage_institutional_bps: float = 2.0

    # Retail trading commission settings
    commission_per_share: float = 0.005
    commission_per_trade: float = 1.00
    commission_pct: float = 0.001
    commission_minimum: float = 1.00

    # Institutional trading commission settings
    commission_per_share_institutional: float = 0.001
    commission_minimum_institutional: float = 0.50

    # Targets
    default_stop_loss_pct: float = 8.0
    default_target_gain_pct: float = 15.0
    momentum_target_profit_pct: float = 20.0
    momentum_stop_loss_pct: float = 8.0


@dataclass(frozen=True)
class ComplianceRules:
    """Regulatory compliance thresholds."""

    # PDT rules
    pdt_day_trade_limit: int = 4
    pdt_rolling_days: int = 5
    pdt_equity_threshold: float = 25000.0

    # Wash sale
    wash_sale_window_days: int = 30


@dataclass(frozen=True)
class MarketConditionRules:
    """Market condition thresholds."""

    # VIX
    vix_low: int = 15
    vix_normal: int = 20
    vix_elevated: int = 20
    vix_high: int = 30

    # Treasury
    treasury_10y_dovish: float = 3.5
    treasury_10y_hawkish: float = 4.5
    treasury_10y_very_dovish: float = 3.0

    # Put-call ratio
    put_call_bullish: float = 0.7

    # Risk-free rate
    default_risk_free_rate: float = 0.04


@dataclass(frozen=True)
class PaperTradingRules:
    """Paper trading configuration."""

    max_holding_days: int = 60
    default_position_pct: float = 0.05


@dataclass(frozen=True)
class CatalystImpact:
    """Single catalyst event impact configuration."""

    impact: float = 0.0  # -5 to +5 scale
    duration_days: int = 3


@dataclass(frozen=True)
class WatchlistManagementRules:
    """Watchlist automation configuration."""

    # Size limits
    max_watchlist_size: int = 50
    max_daily_additions: int = 5
    max_daily_removals: int = 3

    # Discovery thresholds
    discovery_score_threshold: float = 6.0
    gainers_threshold_pct: float = 5.0
    volume_spike_ratio: float = 2.0
    news_mention_threshold: int = 3

    # Trimming rules
    auto_trim_enabled: bool = True
    min_days_watched: int = 7
    min_score_threshold: float = 4.0
    exclude_portfolio_holdings: bool = True


@dataclass(frozen=True)
class ThesisManagementRules:
    """Thesis generation, validation, and invalidation configuration."""

    # Generation settings
    thesis_generation_enabled: bool = True
    thesis_cache_ttl_hours: int = 24
    max_tokens_per_generation: int = 4096
    max_tokens_per_validation: int = 2048

    # Cross-validation settings
    cross_validation_enabled: bool = True
    min_cross_validation_score: float = 0.5
    auto_flag_low_confidence: bool = True

    # Invalidation behavior
    auto_remove_on_invalidation: bool = True
    version_retention_days: int = 365
    max_versions_per_symbol: int = 50

    # Rate limiting
    max_generations_per_day: int = 10
    generation_cooldown_seconds: int = 60


@dataclass
class TradingRules:
    """Root configuration containing all trading rules."""

    version: str = "1.0.0"
    updated: str = ""
    updated_by: str = ""

    position_sizing: PositionSizingRules = field(default_factory=PositionSizingRules)
    risk_management: RiskManagementRules = field(default_factory=RiskManagementRules)
    technical_thresholds: TechnicalThresholds = field(default_factory=TechnicalThresholds)
    scoring: ScoringRules = field(default_factory=ScoringRules)
    fundamentals: FundamentalThresholds = field(default_factory=FundamentalThresholds)
    signals: SignalThresholds = field(default_factory=SignalThresholds)
    fees: FeeRules = field(default_factory=FeeRules)
    compliance: ComplianceRules = field(default_factory=ComplianceRules)
    market: MarketConditionRules = field(default_factory=MarketConditionRules)
    paper_trading: PaperTradingRules = field(default_factory=PaperTradingRules)
    catalyst_impacts: dict[str, CatalystImpact] = field(default_factory=dict)
    watchlist_management: WatchlistManagementRules = field(default_factory=WatchlistManagementRules)
    thesis_management: ThesisManagementRules = field(default_factory=ThesisManagementRules)
