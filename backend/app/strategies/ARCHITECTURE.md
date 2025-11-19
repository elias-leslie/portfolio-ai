# Dynamic Strategy Generation Architecture

**Last Updated**: 2025-11-19
**Status**: Design Document (Task 4.1)
**Owner**: Autonomous Trading System

---

## Overview

This document defines the architecture for dynamic strategy generation that extends the existing signal_classifier system with research-driven insights.

**Goal**: Generate trading strategies dynamically from market research (news, fundamentals, macro indicators) rather than using hardcoded SignalStrategy parameters.

**Design Philosophy**: Evolution, not revolution - build on existing patterns rather than replacing them.

---

## Current System (Baseline)

### Signal Classification Flow

```
INPUT → NORMALIZE → AVOID CHECK → BUY CHECK → STRENGTH CALCULATION → OUTPUT
```

**8-Confirmation Checkpoint Model**:
1. Price > EMA (uptrend)
2. RSI 30-70 (healthy)
3. MACD > 0 (momentum)
4. Volume ≥ 70% of 20-day avg
5. Company health = EXCELLENT/GOOD
6. News sentiment ≥ 0.2
7. RSI ≤ 70 (not overbought)
8. Price significantly above EMA (2%+)

**Signal Types**: BUY (≥6 confirmations), HOLD (3-5), AVOID (≤2 or negative flags)

**Strengths**:
- ✅ Multi-source (technical, fundamental, news, macro)
- ✅ Cached efficiently (24h TTL fundamentals, 8h news)
- ✅ Type-safe (Pydantic models)
- ✅ Extensible (Strategy protocol)
- ✅ Battle-tested (production backtests working)

**Limitations**:
- ❌ Equal weight confirmations (all count as 1/8)
- ❌ No research context (news is single scalar -1 to +1)
- ❌ No regime awareness (Fear & Greed unused)
- ❌ No parameter adaptation (thresholds hardcoded)

---

## Dynamic Strategy System (Phase B)

### Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Research Aggregation Service                      │
│  Collect + structure market research from all sources       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Strategy Generation Agent (LLM)                   │
│  Analyze research → Generate strategy config JSON           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: Parameter Optimization (Backtesting)              │
│  Test parameter ranges → Select best configuration          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 4: Strategy Storage & Versioning (Database)          │
│  Store strategy + research context + backtest metrics       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 5: Dynamic Strategy Execution (Workflow)             │
│  Select best strategy → Execute paper trade validation      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Layer 6: Performance Tracking (Monitoring)                 │
│  Track strategy success → Archive underperformers           │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Research Aggregation Service

**File**: `backend/app/strategies/research_aggregator.py`

**Purpose**: Collect and structure market research from all available sources.

### Data Sources

| Source | What to Collect | Timeframe | Access Pattern |
|--------|-----------------|-----------|----------------|
| **News** | Sentiment trend, event clusters, material flags | 30 days rolling | `app/services/news_sentiment.py` |
| **Fundamentals** | Health classification, valuation metrics, growth trends | Latest + 1yr history | `app/watchlist/fundamentals.py` |
| **Technical** | Trend strength, momentum, volume profile | Latest + 252 days | `app/analytics/indicators.py` |
| **Macro** | Fear & Greed score, regime classification | Latest | `app/api/market.py` |
| **Sector** | Relative strength vs SPY, rotation phase | Latest + 30 days | New: `app/analytics/sector_momentum.py` |

### Output Schema

```python
@dataclass
class ResearchInsights:
    """Structured research summary for strategy generation."""

    symbol: str
    as_of_date: date

    # News Intelligence (30-day rolling)
    news_sentiment_trend: str  # "improving", "stable", "deteriorating"
    news_sentiment_score: float  # -1.0 to +1.0 (current)
    news_sentiment_7d_avg: float  # 7-day rolling average
    news_sentiment_30d_avg: float  # 30-day rolling average
    material_events: list[str]  # ["earnings_beat", "product_launch"]
    news_volume: int  # Article count in 30 days
    news_confidence: float  # 0-1 (based on article count + source quality)

    # Fundamental Analysis
    company_health: str  # "EXCELLENT", "GOOD", "WEAK"
    fundamental_score: int  # 0-100 (4-pillar composite)
    valuation_tier: str  # "undervalued", "fair", "overvalued"
    growth_tier: str  # "accelerating", "stable", "slowing"
    profitability_tier: str  # "excellent", "good", "weak"
    debt_tier: str  # "low", "moderate", "high"
    analyst_consensus: float  # 1.0-5.0 (1=strong buy, 5=sell)
    fundamental_confidence: float  # 0-1 (based on data completeness)

    # Technical Analysis
    trend_strength: str  # "strong_up", "weak_up", "neutral", "weak_down", "strong_down"
    trend_duration_days: int  # How long current trend has lasted
    momentum_rating: str  # "accelerating", "steady", "decelerating"
    volume_profile: str  # "increasing", "stable", "decreasing"
    rsi_zone: str  # "oversold", "healthy", "overbought"
    price_vs_ma: dict[str, float]  # {"20d": 1.05, "50d": 1.08, "200d": 1.12}
    technical_confidence: float  # 0-1 (always 1.0 if we have 252 days data)

    # Macro Context
    market_regime: str  # "bull", "bear", "range", "volatile"
    fear_greed_score: int  # 0-100
    fear_greed_classification: str  # "extreme_fear", "fear", "neutral", "greed", "extreme_greed"
    sector_rotation_phase: str  # "early_cycle", "mid_cycle", "late_cycle", "recession"

    # Sector Relative Strength (NEW)
    sector: str  # e.g., "Technology", "Healthcare"
    sector_momentum: str  # "leading", "in_line", "lagging"
    sector_vs_spy_30d: float  # +5.2 = outperforming by 5.2%
    sector_rotation_signal: str  # "rotate_in", "hold", "rotate_out"

    # Composite Assessment
    overall_confidence: float  # 0-1 (weighted average of source confidences)
    research_quality: str  # "high", "medium", "low"
    last_updated: datetime
```

### Implementation Notes

- **Caching**: Cache ResearchInsights for 6 hours (balance freshness vs API cost)
- **Fallback**: If any source unavailable, set confidence=0.0 for that dimension
- **Sector Logic**: Use existing sector ETF mappings from `app/watchlist/scoring_service/`
- **Macro Regime**: Classify based on Fear & Greed + VIX + trend direction
  - Bull: FG > 60, VIX < 20, SPY uptrend
  - Bear: FG < 40, VIX > 25, SPY downtrend
  - Volatile: VIX > 30 regardless of trend
  - Range: None of above (choppy market)

---

## Layer 2: Strategy Generation Agent

**File**: `backend/app/agents/strategy_generator.py`

**Purpose**: LLM agent that analyzes ResearchInsights and generates StrategyConfig.

### System Prompt Template

```
You are a quantitative trading strategist. Your job is to analyze market research and generate a trading strategy configuration.

**Input Research Summary**:
{research_insights_json}

**Your Task**:
1. Analyze the research across all dimensions (news, fundamentals, technical, macro, sector)
2. Identify the dominant market theme (e.g., "strong momentum with positive earnings", "sector rotation opportunity")
3. Design a strategy that capitalizes on this theme
4. Generate a JSON configuration with strategy parameters

**Strategy Types to Consider**:
- **Momentum**: Strong uptrend + positive news + sector strength → aggressive entries
- **Value**: Undervalued fundamentals + improving sentiment → patient entries
- **Event**: Material news event + earnings proximity → short-term tactical
- **Reversal**: Oversold technical + improving fundamentals → contrarian entries
- **Defensive**: High volatility + weak sentiment → conservative entries only

**Output JSON Schema**:
{
  "strategy_type": "momentum|value|event|reversal|defensive",
  "reasoning": "2-3 sentence explanation of why this strategy fits the research",
  "confidence": 0.7,  // 0.0-1.0 based on research quality

  "parameters": {
    // Confirmation weights (must sum to 1.0)
    "weight_price_trend": 0.20,
    "weight_rsi_health": 0.10,
    "weight_momentum": 0.15,
    "weight_volume": 0.10,
    "weight_fundamentals": 0.15,
    "weight_news_sentiment": 0.20,
    "weight_sector_alignment": 0.10,

    // Entry thresholds
    "min_confirmations": 6,  // Out of 8 checks
    "min_weighted_score": 0.65,  // Weighted score threshold

    // Risk management
    "stop_loss_atr_multiplier": 2.0,
    "max_holding_days": 60,
    "position_sizing_method": "fixed_dollars",
    "position_size_value": 10000.00,

    // Strategy-specific overrides
    "rsi_oversold_threshold": 30,
    "rsi_overbought_threshold": 70,
    "volume_multiplier_threshold": 0.7,
    "news_sentiment_threshold": 0.2
  },

  "expected_characteristics": {
    "avg_holding_period_days": 45,
    "expected_win_rate": 0.55,
    "expected_sharpe": 1.3,
    "risk_level": "medium"
  }
}

**Critical Rules**:
- Weights must sum to exactly 1.0
- All thresholds must be within reasonable ranges (RSI 0-100, sentiment -1 to +1)
- Confidence must reflect research quality (low quality = lower confidence)
- If research is insufficient (confidence < 0.5), recommend "no_strategy" type
```

### Agent Configuration

```python
agent_config = {
    "name": "strategy_generator",
    "system_prompt": STRATEGY_GENERATOR_PROMPT,
    "tools": [
        "get_news",  # Can fetch additional news if needed
        "get_price_data",  # Can check current prices
        "get_economic_data",  # Can check macro indicators
    ],
    "model": "gemini",  # Primary (fast + cheap)
    "fallback_model": "claude",  # Fallback (more accurate)
    "max_tokens": 2000,
    "temperature": 0.3,  # Low temperature for consistent strategy generation
}
```

### Output Validation

```python
class StrategyGenerationResult(BaseModel):
    """Agent output from strategy generation."""

    strategy_type: Literal["momentum", "value", "event", "reversal", "defensive", "no_strategy"]
    reasoning: str = Field(min_length=50, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)

    parameters: StrategyParameters
    expected_characteristics: ExpectedCharacteristics

    @validator("parameters")
    def validate_weights_sum(cls, v):
        weights = [
            v.weight_price_trend,
            v.weight_rsi_health,
            v.weight_momentum,
            v.weight_volume,
            v.weight_fundamentals,
            v.weight_news_sentiment,
            v.weight_sector_alignment,
        ]
        total = sum(weights)
        if not 0.99 <= total <= 1.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        return v
```

---

## Layer 3: Parameter Optimization

**File**: `backend/app/strategies/optimizer.py`

**Purpose**: Test parameter ranges via backtesting, select optimal configuration.

### Optimization Approach: Walk-Forward Validation

**Problem**: Overfitting to historical data (parameter tuning on full dataset)

**Solution**: Split data into training and validation windows

```
┌─────────────────┬─────────────────┬─────────────────┬─────────────────┐
│  Training 1     │  Validation 1   │                 │                 │
│  (optimize)     │  (verify)       │                 │                 │
└─────────────────┴─────────────────┴─────────────────┴─────────────────┘
                  ┌─────────────────┬─────────────────┬─────────────────┐
                  │  Training 2     │  Validation 2   │                 │
                  │  (optimize)     │  (verify)       │                 │
                  └─────────────────┴─────────────────┴─────────────────┘
                                    ┌─────────────────┬─────────────────┐
                                    │  Training 3     │  Validation 3   │
                                    │  (optimize)     │  (verify)       │
                                    └─────────────────┴─────────────────┘
```

**Window Sizes**:
- Training: 180 days (~6 months)
- Validation: 60 days (~2 months)
- Step: 60 days (roll forward 2 months each iteration)

### Parameter Ranges to Test

```python
OPTIMIZATION_RANGES = {
    # Confirmation weights (test combinations, ensure sum=1.0)
    "weight_price_trend": [0.10, 0.15, 0.20, 0.25],
    "weight_fundamentals": [0.10, 0.15, 0.20, 0.25],
    "weight_news_sentiment": [0.10, 0.15, 0.20, 0.25],
    "weight_sector_alignment": [0.05, 0.10, 0.15, 0.20],

    # Entry thresholds
    "min_confirmations": [5, 6, 7],
    "min_weighted_score": [0.60, 0.65, 0.70],

    # Risk management
    "stop_loss_atr_multiplier": [1.5, 2.0, 2.5],
    "max_holding_days": [30, 45, 60, 90],

    # Technical thresholds
    "rsi_oversold_threshold": [25, 30, 35],
    "rsi_overbought_threshold": [65, 70, 75],
    "volume_multiplier_threshold": [0.6, 0.7, 0.8],
}
```

### Optimization Metrics

**Primary**: Sharpe ratio (risk-adjusted returns)
**Secondary**: Win rate, max drawdown, profit factor

**Selection Logic**:
1. Filter: Sharpe > 1.0 on ALL validation windows
2. Filter: Max drawdown < 25% on ALL validation windows
3. Rank: By average Sharpe across validation windows
4. Select: Top configuration

### Implementation

```python
async def optimize_strategy_parameters(
    symbol: str,
    strategy_template: StrategyGenerationResult,
    lookback_days: int = 365,
) -> OptimizedStrategyConfig:
    """Optimize strategy parameters using walk-forward validation.

    Args:
        symbol: Stock ticker
        strategy_template: Base strategy from agent
        lookback_days: Historical data to use (default 1 year)

    Returns:
        Optimized configuration with backtest metrics
    """
    # 1. Generate parameter combinations (limited grid search)
    param_combinations = generate_param_grid(strategy_template, max_combinations=50)

    # 2. Walk-forward validation (3 windows)
    results = []
    for params in param_combinations:
        window_results = []
        for train_start, train_end, val_start, val_end in walk_forward_windows(lookback_days):
            # Train: Optimize on this window (already done, just validate)
            val_result = await run_backtest(
                symbol=symbol,
                start_date=val_start,
                end_date=val_end,
                strategy_params=params,
            )
            window_results.append(val_result)

        # 3. Aggregate metrics across windows
        avg_sharpe = mean([r.sharpe_ratio for r in window_results])
        max_drawdown = max([r.max_drawdown_pct for r in window_results])
        avg_win_rate = mean([r.win_rate for r in window_results])

        results.append({
            "params": params,
            "avg_sharpe": avg_sharpe,
            "max_drawdown": max_drawdown,
            "avg_win_rate": avg_win_rate,
            "window_results": window_results,
        })

    # 4. Select best configuration
    viable = [r for r in results if r["avg_sharpe"] > 1.0 and r["max_drawdown"] < 0.25]
    if not viable:
        raise ValueError("No viable strategies found (all failed Sharpe or drawdown filters)")

    best = max(viable, key=lambda x: x["avg_sharpe"])

    return OptimizedStrategyConfig(
        strategy_type=strategy_template.strategy_type,
        parameters=best["params"],
        optimization_metrics=best["window_results"],
        confidence=strategy_template.confidence * 0.9,  # Slight penalty for optimization uncertainty
    )
```

**Complexity Management**: Start with 50 combinations max (can expand to 200+ in Phase C)

---

## Layer 4: Strategy Storage & Versioning

**Database Table**: `strategy_definitions`

```sql
CREATE TABLE strategy_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,  -- e.g., "AAPL_Momentum_2024Q4"
    symbol VARCHAR(10) NOT NULL,
    strategy_type VARCHAR(50) NOT NULL,  -- momentum, value, event, etc.

    -- Strategy configuration (JSONB)
    parameters JSONB NOT NULL,  -- Full StrategyParameters JSON

    -- Research context (what informed this strategy)
    research_summary JSONB NOT NULL,  -- ResearchInsights snapshot
    generation_reasoning TEXT,  -- Agent's explanation

    -- Performance metrics (from optimization)
    backtest_metrics JSONB NOT NULL,  -- Walk-forward results
    expected_sharpe NUMERIC(10, 4),
    expected_win_rate NUMERIC(5, 4),
    expected_max_drawdown NUMERIC(5, 4),

    -- Metadata
    created_by VARCHAR(255),  -- "agent_run:{uuid}" or "manual"
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    version INT NOT NULL DEFAULT 1,  -- Increment on parameter changes

    -- Status tracking
    status VARCHAR(50) NOT NULL DEFAULT 'testing',  -- testing, active, archived
    activation_date TIMESTAMP WITH TIME ZONE,
    archive_date TIMESTAMP WITH TIME ZONE,
    archive_reason TEXT,

    -- Performance tracking (updated daily)
    live_trades_count INT DEFAULT 0,
    live_win_rate NUMERIC(5, 4),
    live_sharpe_ratio NUMERIC(10, 4),
    last_used_at TIMESTAMP WITH TIME ZONE,

    -- Indexes
    UNIQUE(symbol, name, version),
    INDEX idx_strategy_status ON strategy_definitions(status, symbol),
    INDEX idx_strategy_type ON strategy_definitions(strategy_type, status)
);

CREATE TABLE strategy_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID NOT NULL REFERENCES strategy_definitions(id),
    date DATE NOT NULL,

    -- Daily metrics
    trades_today INT DEFAULT 0,
    wins_today INT DEFAULT 0,
    losses_today INT DEFAULT 0,
    pnl_today NUMERIC(15, 2) DEFAULT 0,

    -- Rolling metrics (30-day)
    trades_30d INT DEFAULT 0,
    win_rate_30d NUMERIC(5, 4),
    sharpe_ratio_30d NUMERIC(10, 4),
    max_drawdown_30d NUMERIC(5, 4),

    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    notes TEXT,

    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE(strategy_id, date),
    INDEX idx_performance_date ON strategy_performance(date DESC),
    INDEX idx_performance_status ON strategy_performance(status, date DESC)
);
```

### Versioning Strategy

**When to create new version**:
- Parameter changes (even minor)
- Research context changes significantly
- Strategy fails performance review

**How**:
1. Query: `SELECT MAX(version) FROM strategy_definitions WHERE symbol = ? AND name = ?`
2. Insert: New row with `version = max_version + 1`
3. Archive: Update old version `status = 'archived', archive_reason = 'superseded_by_v{new_version}'`

**Rollback**: Can reactivate old version if new version underperforms

---

## Layer 5: Dynamic Strategy Execution

**File**: `backend/app/agents/workflows/strategy_research_workflow.py`

**Purpose**: Orchestrate complete strategy generation pipeline.

### Workflow Steps

```python
async def strategy_research_workflow(
    symbol: str,
    force_regenerate: bool = False,
) -> WorkflowResult:
    """Generate new strategy from market research.

    Steps:
    1. Check if active strategy exists (skip if exists unless force=True)
    2. Aggregate market research
    3. Generate strategy via LLM agent
    4. Optimize parameters via backtesting
    5. Store strategy in database
    6. Commit to git with research summary

    Args:
        symbol: Stock ticker
        force_regenerate: Regenerate even if active strategy exists

    Returns:
        WorkflowResult with strategy_id and performance metrics
    """
    workflow_id = str(uuid.uuid4())

    try:
        # Step 1: Check existing strategy
        existing = await get_active_strategy(symbol)
        if existing and not force_regenerate:
            return WorkflowResult(
                workflow_id=workflow_id,
                status="skipped",
                message=f"Active strategy exists: {existing.name} (v{existing.version})",
            )

        # Step 2: Aggregate research
        research = await research_aggregator.aggregate_research(symbol, lookback_days=30)
        if research.overall_confidence < 0.5:
            return WorkflowResult(
                workflow_id=workflow_id,
                status="blocked",
                message=f"Insufficient research quality (confidence={research.overall_confidence:.2f})",
            )

        # Step 3: Generate strategy via agent
        agent_result = await strategy_generator_agent.generate_strategy(research)
        if agent_result.strategy_type == "no_strategy":
            return WorkflowResult(
                workflow_id=workflow_id,
                status="blocked",
                message=f"Agent recommends no strategy: {agent_result.reasoning}",
            )

        # Step 4: Optimize parameters
        optimized = await optimizer.optimize_strategy_parameters(
            symbol=symbol,
            strategy_template=agent_result,
            lookback_days=365,
        )

        # Step 5: Store in database
        strategy_id = await store_strategy(
            symbol=symbol,
            strategy_type=agent_result.strategy_type,
            parameters=optimized.parameters,
            research_summary=research,
            generation_reasoning=agent_result.reasoning,
            backtest_metrics=optimized.optimization_metrics,
            created_by=f"workflow:{workflow_id}",
            status="testing",  # Start in testing mode
        )

        # Step 6: Commit to git
        snapshot = {
            "workflow_id": workflow_id,
            "symbol": symbol,
            "strategy_id": strategy_id,
            "strategy_type": agent_result.strategy_type,
            "research_summary": asdict(research),
            "agent_reasoning": agent_result.reasoning,
            "backtest_metrics": optimized.optimization_metrics,
            "confidence": optimized.confidence,
        }

        commit_result = await git_automation.commit_workflow_result(
            workflow_type="strategy_research",
            snapshot_data=snapshot,
            summary=f"Generated {agent_result.strategy_type} strategy for {symbol} (confidence={optimized.confidence:.2f})",
        )

        return WorkflowResult(
            workflow_id=workflow_id,
            status="completed",
            strategy_id=strategy_id,
            commit_sha=commit_result["commit_sha"],
            message=f"Strategy generated successfully (Sharpe={optimized.optimization_metrics[0].sharpe_ratio:.2f})",
        )

    except Exception as e:
        logger.exception(f"Strategy research workflow failed: {e}")
        return WorkflowResult(
            workflow_id=workflow_id,
            status="failed",
            error_message=str(e),
        )
```

### Integration with Paper Trading

**File**: `backend/app/agents/workflows/paper_trade_validation_workflow.py` (UPDATE)

**Changes**:
1. Query for active strategy: `SELECT * FROM strategy_definitions WHERE symbol = ? AND status = 'active' ORDER BY version DESC LIMIT 1`
2. If custom strategy exists: Use its parameters instead of default SignalStrategy
3. Log which strategy was used: Add `strategy_id` to trade metadata
4. Fallback: If no custom strategy, use SignalStrategy (current behavior)

```python
# BEFORE (Task 3 - current state)
backtest_result = await execute_run_backtest(
    ticker=ticker,
    start_date=start_date,
    end_date=end_date,
    strategy="signal_classifier",  # HARDCODED
    min_signal_strength=7,
    max_holding_days=60,
    ...
)

# AFTER (Task 4.7 - dynamic strategies)
strategy = await get_active_strategy(ticker)
if strategy:
    # Use dynamic strategy
    backtest_result = await execute_run_backtest_with_strategy(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        strategy_config=strategy.parameters,  # DYNAMIC
        strategy_id=strategy.id,
    )
    logger.info(f"Using dynamic strategy: {strategy.name} v{strategy.version}")
else:
    # Fallback to default
    backtest_result = await execute_run_backtest(
        ticker=ticker,
        strategy="signal_classifier",  # DEFAULT
        ...
    )
    logger.info("Using default SignalStrategy (no custom strategy found)")
```

---

## Layer 6: Performance Tracking

**File**: `backend/app/tasks/strategy_monitoring_tasks.py`

**Purpose**: Daily evaluation of active strategies, archive underperformers.

### Daily Task: Evaluate Strategy Performance

```python
@celery_app.task(name="app.tasks.strategy_monitoring_tasks.evaluate_strategy_performance")
def evaluate_strategy_performance() -> dict[str, Any]:
    """Evaluate all active strategies and archive underperformers.

    Schedule: Daily at 04:00 UTC (after market data updated)

    Logic:
    1. For each active strategy:
       - Calculate 30-day rolling metrics (Sharpe, win rate, max drawdown)
       - Compare to expected metrics from backtest
       - Deactivate if performance < 70% of expected for >30 days
    2. Update strategy_performance table with daily metrics
    3. Send alerts if strategy underperforming

    Returns:
        Summary of strategies evaluated and actions taken
    """
    conn = ConnectionManager.get_connection()

    # Get all active strategies
    active_strategies = conn.execute_query(
        "SELECT * FROM strategy_definitions WHERE status = 'active'"
    )

    results = []
    for strategy in active_strategies:
        # Calculate 30-day metrics from paper_trade_transactions
        metrics = calculate_rolling_metrics(
            strategy_id=strategy["id"],
            window_days=30,
        )

        # Compare to expected metrics
        expected_sharpe = strategy["expected_sharpe"]
        actual_sharpe = metrics["sharpe_ratio_30d"]

        performance_ratio = actual_sharpe / expected_sharpe if expected_sharpe > 0 else 0

        # Decision logic
        if performance_ratio < 0.7 and metrics["days_since_activation"] > 30:
            # Underperforming for >30 days → Archive
            conn.execute_query(
                """
                UPDATE strategy_definitions
                SET status = 'archived',
                    archive_date = NOW(),
                    archive_reason = %s
                WHERE id = %s
                """,
                (
                    f"Underperforming: {actual_sharpe:.2f} Sharpe vs {expected_sharpe:.2f} expected ({performance_ratio:.1%})",
                    strategy["id"],
                ),
            )
            results.append(f"Archived {strategy['name']}: {performance_ratio:.1%} of expected performance")

        # Update performance tracking table
        conn.execute_query(
            """
            INSERT INTO strategy_performance (strategy_id, date, trades_30d, win_rate_30d, sharpe_ratio_30d, max_drawdown_30d, status)
            VALUES (%s, CURRENT_DATE, %s, %s, %s, %s, %s)
            ON CONFLICT (strategy_id, date) DO UPDATE SET
                trades_30d = EXCLUDED.trades_30d,
                win_rate_30d = EXCLUDED.win_rate_30d,
                sharpe_ratio_30d = EXCLUDED.sharpe_ratio_30d,
                max_drawdown_30d = EXCLUDED.max_drawdown_30d,
                status = EXCLUDED.status
            """,
            (
                strategy["id"],
                metrics["trades_30d"],
                metrics["win_rate_30d"],
                metrics["sharpe_ratio_30d"],
                metrics["max_drawdown_30d"],
                "underperforming" if performance_ratio < 0.7 else "active",
            ),
        )

    return {
        "strategies_evaluated": len(active_strategies),
        "strategies_archived": sum(1 for r in results if "Archived" in r),
        "details": results,
    }
```

### Celery Beat Schedule

```python
# backend/app/celery_schedules.py

"evaluate-strategy-performance": {
    "task": "app.tasks.strategy_monitoring_tasks.evaluate_strategy_performance",
    "schedule": crontab(hour=4, minute=0),  # Daily at 04:00 UTC
    "options": {"expires": 3600},
},

"generate-weekly-strategies": {
    "task": "app.tasks.workflow_tasks.weekly_strategy_generation",
    "schedule": crontab(hour=5, minute=0, day_of_week=0),  # Sunday 05:00 UTC
    "options": {"expires": 7200},
},
```

---

## API Endpoints (Layer 9)

**File**: `backend/app/api/strategies.py`

### Endpoints

```python
# List all strategies with filtering
GET /api/strategies?symbol=AAPL&status=active&strategy_type=momentum
Response: {
    "strategies": [
        {
            "id": "uuid",
            "name": "AAPL_Momentum_2024Q4",
            "symbol": "AAPL",
            "strategy_type": "momentum",
            "status": "active",
            "version": 3,
            "expected_sharpe": 1.45,
            "live_sharpe_ratio": 1.38,
            "live_win_rate": 0.58,
            "trades_count": 12,
            "created_at": "2024-11-15T05:00:00Z",
            "activation_date": "2024-11-20T00:00:00Z"
        }
    ],
    "total": 1
}

# Get strategy details with full config
GET /api/strategies/{strategy_id}
Response: {
    "strategy": {
        "id": "uuid",
        "name": "AAPL_Momentum_2024Q4",
        "parameters": { ... },  // Full StrategyParameters
        "research_summary": { ... },  // ResearchInsights snapshot
        "generation_reasoning": "Agent explanation",
        "backtest_metrics": [ ... ],  // Walk-forward results
        "performance_history": [ ... ]  // 30 days of daily metrics
    }
}

# Trigger strategy generation for symbol
POST /api/strategies/generate
Body: {
    "symbol": "AAPL",
    "force_regenerate": false
}
Response: {
    "workflow_id": "uuid",
    "status": "pending",
    "message": "Strategy generation started"
}

# Update strategy status (activate/archive)
PATCH /api/strategies/{strategy_id}
Body: {
    "status": "active"
}
Response: {
    "strategy": { ... },
    "message": "Strategy activated"
}

# Get performance comparison (backtest vs live)
GET /api/strategies/{strategy_id}/performance
Response: {
    "expected": {
        "sharpe": 1.45,
        "win_rate": 0.60,
        "max_drawdown": 0.18
    },
    "actual_30d": {
        "sharpe": 1.38,
        "win_rate": 0.58,
        "max_drawdown": 0.15
    },
    "performance_ratio": 0.95,
    "status": "meeting_expectations"
}
```

---

## Testing Strategy

### Unit Tests (Layer 10)

**File**: `backend/tests/unit/strategies/test_research_aggregator.py`

- Test research aggregation with mock data sources
- Test confidence scoring logic
- Test fallback behavior when sources unavailable

**File**: `backend/tests/unit/strategies/test_strategy_generator.py`

- Test agent prompt formatting
- Test output validation (weights sum to 1.0)
- Test strategy type selection logic

**File**: `backend/tests/unit/strategies/test_optimizer.py`

- Test parameter grid generation
- Test walk-forward window calculation
- Test metric aggregation logic

**File**: `backend/tests/unit/strategies/test_storage.py`

- Test strategy versioning logic
- Test performance tracking updates
- Test status transitions (testing → active → archived)

### Integration Tests (Layer 11)

**File**: `backend/tests/integration/test_strategy_pipeline.py`

- **Test 1**: Generate strategy for AAPL
  - Verify research aggregated from all sources
  - Verify agent generated valid strategy JSON
  - Verify parameters optimized via backtest
  - Verify strategy stored in database with correct status

- **Test 2**: Use dynamic strategy in paper trade workflow
  - Create test strategy in database
  - Trigger paper_trade_validation_workflow
  - Verify workflow used custom strategy (not default)
  - Verify trade metadata includes strategy_id

- **Test 3**: Performance tracking and archival
  - Create strategy with poor live performance
  - Run evaluate_strategy_performance task
  - Verify strategy archived with correct reason

---

## Phased Rollout Plan

### Phase B.1: Research Aggregation (Task 4.2)
**Deliverables**:
- `research_aggregator.py` with ResearchInsights dataclass
- Unit tests for aggregation logic
- 6-hour caching via Redis

**Success**: Can call `aggregate_research("AAPL")` and get complete research summary

---

### Phase B.2: Strategy Generation Agent (Task 4.3)
**Deliverables**:
- `strategy_generator.py` with LLM agent
- System prompt template with JSON schema
- Output validation (weights, thresholds, ranges)

**Success**: Agent generates valid StrategyGenerationResult from ResearchInsights

---

### Phase B.3: Parameter Optimization (Task 4.4)
**Deliverables**:
- `optimizer.py` with walk-forward validation
- Parameter grid generation
- Metric aggregation and selection logic

**Success**: Optimizer produces better Sharpe ratio than base strategy

---

### Phase B.4: Strategy Storage (Task 4.5)
**Deliverables**:
- Migration: Create `strategy_definitions` and `strategy_performance` tables
- CRUD operations for strategy management
- Versioning logic

**Success**: Can store, retrieve, and version strategies

---

### Phase B.5: Workflow Integration (Tasks 4.6-4.7)
**Deliverables**:
- `strategy_research_workflow.py` orchestration
- Update `paper_trade_validation_workflow.py` to use dynamic strategies
- Git automation for strategy commits

**Success**: Can generate strategy end-to-end, use it in paper trades

---

### Phase B.6: Performance Tracking (Task 4.8)
**Deliverables**:
- `evaluate_strategy_performance` Celery task
- Daily metrics calculation
- Archival logic for underperformers

**Success**: Strategies automatically archived if underperforming

---

### Phase B.7: API & Testing (Tasks 4.9-4.11)
**Deliverables**:
- `api/strategies.py` with 5 endpoints
- 10+ unit tests covering all modules
- 3 integration tests for complete pipeline

**Success**: Can manage strategies via API, all tests passing

---

## Success Metrics

**Technical**:
- ✅ All 10+ unit tests passing
- ✅ All 3 integration tests passing
- ✅ Mypy --strict compliance maintained
- ✅ Ruff linting passing

**Functional**:
- ✅ Research aggregation returns high-confidence insights (>0.7)
- ✅ Agent generates valid strategies with reasonable parameters
- ✅ Optimizer improves Sharpe by ≥10% vs base strategy
- ✅ Strategies stored with complete audit trail
- ✅ Paper trades use dynamic strategies when available
- ✅ Performance tracking archives underperformers automatically

**Operational**:
- ✅ Strategy generation workflow completes in <10 minutes
- ✅ Weekly strategy generation runs autonomously via Celery beat
- ✅ Git commits contain complete strategy context
- ✅ UI can display strategy metrics (via API)

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Agent generates invalid parameters | MEDIUM | HIGH | Strict Pydantic validation, weight sum checks |
| Optimization overfits historical data | HIGH | MEDIUM | Walk-forward validation (3 windows), conservative selection |
| Strategy performs worse than baseline | MEDIUM | MEDIUM | Require Sharpe > 1.0, archive if live < 70% expected |
| LLM costs too high for weekly generation | LOW | MEDIUM | Use Gemini (cheap), cache research for 6h, limit to top 20 watchlist symbols |
| Complexity slows development | MEDIUM | HIGH | Start simple (Task 4.2-4.4), iterate to full pipeline (4.5-4.11) |

---

## Future Enhancements (Phase C)

**Beyond MVP**:
- Multi-symbol strategies (portfolio-level optimization)
- Ensemble strategies (combine multiple signals)
- Market regime detection (switch strategies based on VIX/Fear & Greed)
- Real-time parameter adaptation (adjust during market hours)
- Strategy blending (50% momentum + 50% value)
- Advanced optimization (genetic algorithms, Bayesian optimization)
- Strategy backtesting dashboard (compare multiple strategies visually)

---

## Appendix: File Structure

```
backend/app/strategies/
├── ARCHITECTURE.md (this file)
├── __init__.py
├── research_aggregator.py  # Layer 1: Collect research
├── strategy_generator.py   # Layer 2: LLM agent
├── optimizer.py             # Layer 3: Parameter optimization
├── storage.py               # Layer 4: Database operations
└── models.py                # Data models (ResearchInsights, StrategyConfig, etc.)

backend/app/agents/workflows/
├── strategy_research_workflow.py  # Layer 5: Orchestration

backend/app/tasks/
├── strategy_monitoring_tasks.py  # Layer 6: Performance tracking

backend/app/api/
├── strategies.py  # Layer 9: REST endpoints

backend/tests/unit/strategies/
├── test_research_aggregator.py
├── test_strategy_generator.py
├── test_optimizer.py
└── test_storage.py

backend/tests/integration/
├── test_strategy_pipeline.py
```

---

**End of Architecture Document**
