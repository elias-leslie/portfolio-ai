# Task List: StrategyLab Service Extraction (P4)

**PRD**: Architecture Modularity Review - Priority 4
**Status**: Ready
**Completion**: 0%
**Effort to Complete**: High (3-4 week sprint)
**Last Updated**: 2025-12-16

---

## MANDATORY: Verify Before Starting

**⚠️ LOCAL AGENT: Before implementing ANY step below, you MUST:**

1. **Analyze current backtest/strategy system**:
   ```bash
   # Review backtest system
   find ~/portfolio-ai/backend/app/backtest -name "*.py" -exec wc -l {} +

   # Review strategy system
   find ~/portfolio-ai/backend/app/strategies -name "*.py" -exec wc -l {} +

   # Review analytics
   find ~/portfolio-ai/backend/app/analytics -name "*.py" -exec wc -l {} +

   # Count total LOC in these systems
   find ~/portfolio-ai/backend/app/{backtest,strategies,analytics} -name "*.py" -exec wc -l {} + | tail -1
   ```

2. **Understand database dependencies**:
   ```bash
   # Backtest-related tables
   psql -d portfolio_ai -c "\dt" | grep -E "(backtest|strategy|trade)"

   # Review schema
   psql -d portfolio_ai -c "\d+ backtest_runs"
   psql -d portfolio_ai -c "\d+ paper_trades"
   psql -d portfolio_ai -c "\d+ strategies"
   ```

3. **Map dependencies**:
   - What portfolio-specific logic is in backtester?
   - What's generic vs domain-specific in strategies?
   - How tightly coupled is analytics to portfolio data?
   - Can backtest run without portfolio context?

4. **Review API surface**:
   ```bash
   # What endpoints expose backtest/strategy functionality?
   grep -r "backtest\|strateg" ~/portfolio-ai/backend/app/api/

   # What Celery tasks are involved?
   grep -r "backtest\|strateg" ~/portfolio-ai/backend/app/tasks/
   ```

5. **Update this plan** based on findings
6. **Create bead structure** (epic + phase beads)

---

## Summary

**Goal**: Extract backtesting and strategy systems into standalone **StrategyLab** service that can backtest trading strategies for any portfolio application.

**Why extract:**
- Backtesting is generic (works for any trading strategy)
- Heavy computation (could run on separate infrastructure)
- Reusable across multiple portfolio apps
- Potential commercial product (strategy research platform)

**Challenges:**
- **High complexity** - Deeply integrated with portfolio data model
- Unclear if extraction provides enough value vs complexity
- May be better to refactor in place first (see P3)

**✅ COMPLETE:** (None yet)
**🔄 IN PROGRESS:** Initial planning and verification
**⚠️ NEXT STEPS:** Verify integration depth, assess extraction viability

**⏱️ ESTIMATED REMAINING:** High complexity - 3-4 week sprint (if viable)

---

## What Would Get Extracted

### Backend Components (~15-20k LOC)
```
backend/app/
├── backtest/              → strategylab/backend/app/backtest/
│   ├── engine.py          (core backtest engine)
│   ├── metrics.py         (performance metrics)
│   ├── simulator.py       (trade simulation)
│   └── validator.py       (strategy validation)
├── strategies/            → strategylab/backend/app/strategies/
│   ├── base.py            (strategy interface)
│   ├── optimizer.py       (parameter optimization)
│   ├── research_aggregator.py (strategy research)
│   └── (individual strategies)
└── analytics/             → strategylab/backend/app/analytics/
    ├── indicators.py      (technical indicators)
    ├── metrics.py         (analytics metrics)
    └── performance.py     (performance analytics)
```

### Database Tables
```sql
-- Move these to StrategyLab
CREATE TABLE backtest_runs (...)
CREATE TABLE backtest_results (...)
CREATE TABLE strategies (...)
CREATE TABLE strategy_parameters (...)
CREATE TABLE paper_trades (...)

-- Keep in Portfolio AI (domain-specific)
CREATE TABLE portfolio_positions (...)
CREATE TABLE portfolio_accounts (...)
```

### API Endpoints
```
GET  /api/backtest/runs
POST /api/backtest/run
GET  /api/backtest/results/{run_id}
GET  /api/strategies
POST /api/strategies
GET  /api/strategies/{id}/backtest
```

---

## Critical Question: Should We Extract This?

### Arguments FOR Extraction ✅

**1. Generic Domain**
- Backtesting logic is not portfolio-specific
- Strategies can work with any price data
- Performance metrics are universal

**2. Heavy Computation**
- Backtests can run for hours on large datasets
- Could benefit from dedicated infrastructure
- Parallel execution on multiple strategies

**3. Reusability**
- Any trading app needs backtesting
- Research platforms need strategy testing
- Multiple portfolio apps could share one backtester

**4. Commercial Potential**
- Strategy research platform as a product
- Sell access to backtesting infrastructure
- Community strategy marketplace

### Arguments AGAINST Extraction ❌

**1. Deep Integration**
- Backtester needs portfolio positions (starting point)
- Strategies reference portfolio analytics
- Results feed back into portfolio decisions

**2. Complexity vs Value**
- 3-4 week effort for uncertain ROI
- May not have second client soon
- Internal refactoring (P3) might be better use of time

**3. Shared Data Model**
- Trades, positions, accounts are portfolio-specific
- Extracting creates duplication or complex sync
- Event-driven architecture (P3) might solve this better

**4. Premature Optimization**
- Not currently a bottleneck
- No performance issues requiring separate infrastructure
- YAGNI (You Ain't Gonna Need It)

---

## Recommendation: DEFER P4 Until After P1 + P3

**Proposed sequence:**
1. ✅ **P1: DevVision extraction** - Clear value, immediate ROI
2. ✅ **P3: Internal refactoring** - Event-driven architecture, bounded contexts
3. ⏸️ **Re-evaluate P4** after P1 + P3 complete

**Why defer:**
- P3's event-driven architecture may solve coupling issues without extraction
- Bounded contexts (P3) will clarify if backtest/strategy is truly separable
- DevVision (P1) provides tooling to manage P4 work if we do it later
- No urgent need (not a bottleneck, no second client waiting)

**When to reconsider P4:**
- After P3 refactoring reveals clean boundaries
- If performance becomes a bottleneck
- If we have a second client (research tool, client portfolio app)
- If we want to build a strategy marketplace product

---

## Alternative: Refactor In Place (Part of P3)

Instead of extracting, treat backtest/strategy as **bounded contexts** within Portfolio AI:

```
app/contexts/
├── portfolio/        ← Core domain
├── market/          ← Data sources
├── trading/         ← Order execution (KEEP HERE)
├── backtest/        ← Bounded context (KEEP HERE)
│   ├── domain/      ← Backtest models, strategies
│   ├── services/    ← Backtest engine, simulator
│   └── interfaces/  ← Strategy interface
└── intelligence/    ← AI agents
```

**Benefits:**
- Clean boundaries without extraction overhead
- Event-driven communication with portfolio
- Can extract later if needed (boundaries are clear)
- Faster to implement (part of P3 work)

---

## IF We Decide to Extract: Implementation Plan

### Phase 1: StrategyLab Repository Setup

**Bead**: Create `Phase 1.1: StrategyLab repo setup` with `complexity:small`

- [ ] Create repository structure
- [ ] Backend (FastAPI + Python 3.13)
- [ ] Database schema (PostgreSQL)
- [ ] Core documentation

### Phase 2: Define Strategy Interface

**Bead**: Create `Phase 2.1: Strategy interface design` with `complexity:medium,domains:backend`

```python
# strategylab/backend/app/strategies/base.py
from abc import ABC, abstractmethod

class Strategy(ABC):
    """Base interface for all trading strategies."""

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate buy/sell signals from price data."""
        pass

    @abstractmethod
    def calculate_position_size(self, capital: float, price: float) -> int:
        """Calculate position size for a signal."""
        pass
```

### Phase 3: Extract Backtest Engine

**Bead**: Create `Phase 3.1: Extract backtest engine` with `complexity:large,domains:backend`

- [ ] Copy backtest engine code
- [ ] Remove portfolio-specific dependencies
- [ ] Make it accept generic data sources
- [ ] Implement as pure computation (input data → results)

### Phase 4: Extract Strategies

**Bead**: Create `Phase 4.1: Extract strategies` with `complexity:large,domains:backend`

- [ ] Copy strategy implementations
- [ ] Refactor to use strategy interface
- [ ] Remove portfolio-specific logic
- [ ] Make strategies data-driven (no hard-coded portfolio refs)

### Phase 5: Client Library for Portfolio AI

**Bead**: Create `Phase 5.1: StrategyLab client` with `complexity:medium,domains:backend`

```python
# portfolio-ai uses StrategyLab client
from strategylab import StrategyLabClient

client = StrategyLabClient(api_url="http://localhost:9001")

# Run backtest
result = await client.run_backtest(
    strategy_id="trend-following",
    start_date="2024-01-01",
    end_date="2024-12-31",
    initial_capital=100000,
    symbols=["AAPL", "MSFT", "GOOGL"]
)

# Get metrics
print(f"Total return: {result.total_return_pct}%")
print(f"Sharpe ratio: {result.sharpe_ratio}")
print(f"Max drawdown: {result.max_drawdown_pct}%")
```

---

## Data Ingestion Note

The **DataFountain** concept (multi-source data ingestion) is valuable but should be considered separately:

**Option A: Build DataFountain first (before P4)**
- Provides clean data layer for StrategyLab
- StrategyLab depends on DataFountain for price data
- Sequence: P1 → P3 → DataFountain → StrategyLab

**Option B: Keep data ingestion in Portfolio AI**
- StrategyLab calls Portfolio AI's data endpoints
- Simpler, no new service needed
- Extract DataFountain only if we need it for other projects

**Option C: Embed data adapters in StrategyLab**
- StrategyLab has its own data fetching
- Duplicates logic from Portfolio AI
- Not recommended (violates DRY)

---

## Production Readiness Verification

**IF we proceed with extraction:**

- [ ] StrategyLab runs backtests independently
- [ ] Portfolio AI successfully uses StrategyLab client
- [ ] All strategies migrated and working
- [ ] Performance acceptable (not slower than before)
- [ ] Test coverage ≥80%
- [ ] Documentation complete
- [ ] Migration guide written
- [ ] Portfolio AI codebase reduced by 15-20k LOC

---

## Success Criteria

**StrategyLab is production-ready when:**
1. ✅ Runs backtests for Portfolio AI strategies
2. ✅ Performance metrics match previous implementation
3. ✅ Can accept data from any source (not Portfolio-AI-specific)
4. ✅ Can serve second client application
5. ✅ Parameter optimization works
6. ✅ Strategy validation prevents bad configs

**Marketability indicators:**
- Can onboard new strategy in <10 minutes
- Backtest 1 year of data in <30 seconds
- Supports 10+ simultaneous backtest runs
- Web UI for strategy research (nice-to-have)

---

## Final Recommendation

**DEFER P4 (StrategyLab extraction) until after P1 + P3 complete.**

**Rationale:**
1. P1 (DevVision) has clear, immediate value
2. P3 (refactoring) will clarify boundaries and reduce coupling
3. P4's value is uncertain (no second client, not a bottleneck)
4. Can treat backtest/strategy as bounded contexts in P3 instead
5. Re-evaluate after P1 + P3 prove extraction pattern works

**If we still want P4 later:**
- Boundaries will be clearer after P3 refactoring
- DevVision will help manage the extraction work
- Can extract quickly if we've done P3 properly

---

**Version:** 1.0.0 | **Updated:** 2025-12-16
