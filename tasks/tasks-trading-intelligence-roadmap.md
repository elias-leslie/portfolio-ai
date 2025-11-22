# Task List: Integrated Trading Intelligence Roadmap

**PRD**: (Strategic roadmap outline)
**Status**: Partially Complete (Core Trading Intelligence Built)
**Completion**: 65% (Tasks 2-5 complete, Tasks 6-8 partial)
**Effort**: High
**Updated**: 2025-11-22

---

## Summary

**✅ COMPLETE:** Tasks 2-5 (Fundamentals, Technical, Strategy, Paper Trading - all integrated)
**🔄 PARTIAL:** Tasks 6-8 (LLM integration exists but not as reviewer, Frontend basic, Docs incomplete)
**⚠️ NEXT:** Task 6.0 (LLM reviewer integration), Task 7.0 (Advanced frontend viz), Task 8.0 (Governance framework)

**VERIFIED STATUS 2025-11-22:**
- ✅ Fundamentals: `watchlist/fundamentals.py` (533 lines, 4-pillar scoring, multi-source) - 100% COMPLETE
- ✅ Technical: `analytics/indicators.py` (382 lines, 6 indicators, trend/momentum/volatility) - 100% COMPLETE
- ✅ Strategy: `watchlist/signal_classifier.py` (286 lines, BUY/HOLD/AVOID + style classification) - 100% COMPLETE
- ✅ Paper Trading: `paper_trading.py` + orders/portfolio modules (17KB total, trade tracking) - 100% COMPLETE
- ✅ Backtest: `backtest/` module exists (added Nov 2025, equity curves, Sharpe ratio)
- ⚠️ LLM reviewer: `agents/llm_client.py` exists but not integrated as strategy reviewer - 30% COMPLETE
- ⚠️ Frontend: Signal/style display exists, advanced viz missing - 50% COMPLETE
- ⚠️ Governance: Core docs exist, metrics dashboard/rollout plan missing - 40% COMPLETE

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

- [x] 4.0 Strategy engine ✅ COMPLETE
  - [x] 4.1 Design deterministic rule framework combining news/fundamental/technical features (signal_classifier.py, 286 lines)
  - [x] 4.2 Implement initial strategy set (BUY/HOLD/AVOID signals + 5 trading styles: Index/Trend/Value/Swing/Event)
  - [x] 4.3 Output recommendation metadata (signal_strength 0-10, style classification, rationale text)

- [x] 5.0 Paper trading & evaluation ✅ COMPLETE
  - [x] 5.1 Extend paper trading module to ingest strategy outputs (paper_trading.py + orders/portfolio, 17KB total)
  - [x] 5.2 Build backtest harness replaying historical features + recommendations (backtest/ module with equity curves)
  - [x] 5.3 Store performance metrics, attribution, and drift indicators (idea_outcomes table + backtest_runs/trades/equity)

- [ ] 6.0 LLM reviewer integration (30% COMPLETE)
  - [ ] 6.1 Define reviewer prompts and guardrails (LLM as analyst) - agents/llm_client.py exists
  - [ ] 6.2 Integrate LLM feedback into strategy pipeline (post-analysis only) - NOT IMPLEMENTED
  - [ ] 6.3 Log reviewer insights and disagreements for human oversight - capabilities/insights_router.py partial

- [ ] 7.0 Frontend & UX (50% COMPLETE)
  - [x] 7.1 Surface combined strategy recommendation cards with rationale and sentiment context - BASIC (signals shown)
  - [ ] 7.2 Visualize paper-trade performance and feature contributions - NOT IMPLEMENTED
  - [ ] 7.3 Provide manual override & feedback capture for human users - NOT IMPLEMENTED

- [ ] 8.0 Governance & documentation (40% COMPLETE)
  - [x] 8.1 Update documentation (architecture, roadmap, model governance) - REFRESH_ARCHITECTURE.md + ROADMAP.md exist
  - [ ] 8.2 Establish evaluation metrics dashboard (drift, accuracy, return) - NOT IMPLEMENTED
  - [ ] 8.3 Plan staged rollout (internal users → beta → production) - NOT IMPLEMENTED
