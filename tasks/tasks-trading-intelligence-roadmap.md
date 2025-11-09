# Task List: Integrated Trading Intelligence Roadmap

**PRD**: (Strategic roadmap outline)
**Status**: Partially Complete (Major Components Exist)
**Completion**: 50%
**Effort**: High
**Updated**: 2025-02-14

---

## Summary

**✅ COMPLETE:** Tasks 2.0 (Fundamentals), 3.0 (Technical), 4.0 (Strategy - basic), 5.0 (Paper trading - partial)
**🔄 IN PROGRESS:** None
**⚠️ NEXT:** Task 1.0 (refresh discovery with actual components), Task 6.0 (LLM reviewer), Task 5.2 (backtest harness)

**VERIFIED STATUS 2025-11-09:**
- ✅ Fundamentals service exists: `watchlist/fundamentals.py` (531 lines, 4-pillar scoring)
- ✅ Technical service exists: `analytics/indicators.py` (RSI, MACD, Bollinger, etc.)
- ✅ Strategy engine exists: `watchlist/signal_classifier.py` (224 lines, BUY/HOLD/AVOID classification)
- ✅ Paper trading exists: `analytics/paper_trading.py` (357 lines, trade tracking)
- ⚠️ Scoring pipeline exists: `watchlist/scoring.py`, `calculator.py`, `refresh_processor.py` (1,980 lines total)
- ❌ LLM reviewer: Not implemented
- ❌ Comprehensive backtest harness: Not implemented
- ⚠️ Frontend: Partial (narrative insights exist, strategy cards may need enhancement)

---

## Vision

Leverage combined signals from news (FinBERT + aggregates), fundamentals, and technical indicators to produce deterministic trading recommendations, run them through a paper-trading harness, evaluate performance, and use an LLM (Claude/ChatGPT) as an analyst-style reviewer rather than the execution authority.

---

## Relevant Files

### Create (4 files)
- `backend/app/services/fundamental_service.py` – multi-source fundamentals aggregation + scoring
- `backend/app/services/technical_service.py` – normalized technical feature computation
- `backend/app/strategy/engine.py` – deterministic strategy recommendation pipeline
- `backend/app/evaluation/backtest_runner.py` – historical replay + metrics capture

### Update (key existing files)
- `backend/app/watchlist/refresh_processor.py` (integrate new scores)
- `backend/app/watchlist/models.py` (augment data structures)
- `backend/app/storage/queries.py` (persist new metrics)
- `backend/app/api/portfolio.py` / `watchlist.py` (expose new analytics)
- `backend/app/tasks/watchlist_tasks.py` / `strategy_tasks.py` (schedule refresh + paper trades)
- `frontend/app/watchlist/page.tsx` / `frontend/app/news/page.tsx` (surface combined insights)
- `docs/core/REFRESH_ARCHITECTURE.md`, `docs/core/ROADMAP.md`

---

## Tasks

- [ ] 1.0 Discovery & design
  - [ ] 1.1 Run pre-implementation analysis (Pre-Check) to inventory existing fundamentals/technicals data sources
  - [ ] 1.2 Define canonical feature set (news sentiment, fundamentals, technicals, risk) and storage schema
  - [ ] 1.3 Document target strategy interface (inputs, outputs, scoring, overrides)

- [x] 2.0 Fundamentals pipeline ✅ COMPLETE
  - [x] 2.1 Discover scope using Explore subagent (fundamental data availability, gaps)
  - [x] 2.2 Implement `FundamentalService` with multi-source fallback + caching (watchlist/fundamentals.py, 531 lines)
  - [x] 2.3 Compute normalized fundamental scores (growth, profitability, balance sheet) (4-pillar scoring system)
  - [x] 2.4 Persist scores per snapshot and expose via API (integrated in refresh_processor.py)

- [x] 3.0 Technical signal normalization ✅ COMPLETE
  - [x] 3.1 Audit existing technical indicator coverage (RSI, MACD, Bollinger, SMA/EMA, ATR, Stochastic)
  - [x] 3.2 Implement standardized technical factor scoring (trend, momentum, volatility) (analytics/indicators.py)
  - [x] 3.3 Store factor history for evaluation/backtesting (integrated in watchlist snapshots)

- [x] 4.0 Strategy engine ⚠️ BASIC IMPLEMENTATION COMPLETE
  - [x] 4.1 Design deterministic rule framework combining news/fundamental/technical features (signal_classifier.py)
  - [ ] 4.2 Implement initial strategy set (e.g., trend-following, event-driven) - Only basic BUY/HOLD/AVOID classification exists
  - [x] 4.3 Output recommendation metadata (entry, exit, confidence) for downstream services (confidence 0-10, style classification)

- [x] 5.0 Paper trading & evaluation ⚠️ PARTIAL
  - [x] 5.1 Extend paper trading module to ingest strategy outputs (paper_trading.py, 357 lines, idea_outcomes table)
  - [ ] 5.2 Build backtest harness replaying historical features + recommendations - NOT IMPLEMENTED
  - [x] 5.3 Store performance metrics, attribution, and drift indicators (basic tracking in idea_outcomes)

- [ ] 6.0 LLM reviewer integration
  - [ ] 6.1 Define reviewer prompts and guardrails (LLM as analyst)
  - [ ] 6.2 Integrate LLM feedback into strategy pipeline (post-analysis only)
  - [ ] 6.3 Log reviewer insights and disagreements for human oversight

- [ ] 7.0 Frontend & UX
  - [ ] 7.1 Surface combined strategy recommendation cards with rationale and sentiment context
  - [ ] 7.2 Visualize paper-trade performance and feature contributions
  - [ ] 7.3 Provide manual override & feedback capture for human users

- [ ] 8.0 Governance & documentation
  - [ ] 8.1 Update documentation (architecture, roadmap, model governance)
  - [ ] 8.2 Establish evaluation metrics dashboard (drift, accuracy, return)
  - [ ] 8.3 Plan staged rollout (internal users → beta → production)
