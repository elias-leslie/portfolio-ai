# Autonomous Multi-Agent Trading System: Execution Roadmap

**Date**: 2025-11-14
**Status**: Ready for Execution
**Priority**: HIGH (Vacation deadline)

---

## Executive Summary

**Your Vision**: Autonomous multi-agent system (Gemini + Claude) that performs daily gap analysis, researches strategies using web sources, paper trades autonomously, backtests to validate approaches, manages watchlist (add/remove tickers), tracks results, and commits to git regularly.

**Reality Check**: Your vision requires **4 major task lists** spanning **8-12 weeks** for a thorough implementation. However, we've designed a **phased approach** that delivers a **functional MVP in 1-2 weeks** (before vacation) and completes the full system in 8-12 weeks total.

**What's Ready**:
- ✅ **Task 0060** (CLI Agent Integration) - Updated with multi-agent collaboration (Task 3.7)
- ✅ **Task 0062** (Gap Detection) - Paused, ready to resume
- ✅ **Task 0063** (Backtesting Framework) - NEW, comprehensive task list created
- ✅ **Task 0064** (Paper Trading Engine) - NEW, comprehensive task list created

---

## What We Created Today

### Task 0063: Backtesting Framework (NEW)

**File**: `tasks/tasks-0063-backtesting-framework.md`

**Phase A (Quick MVP - 3-5 days)**:
- Simple date loop replay engine over `day_bars` table (259 days, 39 symbols available)
- Reuse existing `signal_classifier.py` for entry/exit signals
- Track equity curve, Sharpe ratio, win rate, max drawdown
- Single-symbol backtests (no portfolio complexity)
- Store results in new tables: `backtest_runs`, `backtest_trades`, `backtest_equity`
- API endpoint: `POST /api/backtest` for agents to validate strategies

**Phase B (Full Framework - 3-4 weeks after vacation)**:
- Multi-symbol portfolio backtesting with correlation handling
- Walk-forward validation (prevent overfitting)
- Parameter optimization (grid search, Bayesian)
- Realistic slippage/commission modeling
- Benchmark comparison (SPY buy-and-hold, alpha/beta calculation)
- Strategy library templates (Signal-Based, Momentum, Mean Reversion, Sector Rotation)
- Frontend visualization (equity curve charts, drawdown, trade log)

**Infrastructure Reuse**: 70% exists (day_bars data, signal classifier, performance calculators, indicators engine)

---

### Task 0064: Paper Trading Engine (NEW)

**File**: `tasks/tasks-0064-paper-trading-engine.md`

**Phase A (Quick MVP - 3-5 days)**:
- Add `cash_balance` to `portfolio_accounts` (default $100k)
- Create agent tools: `add_ticker`, `remove_ticker`, `create_paper_trade`
- Simple order execution (instant fills at closing price, no slippage)
- Transaction log table for audit trail (`paper_trade_transactions`)
- Ownership tracking: `added_by` field distinguishes agent-added vs user-added tickers
- **Autonomous watchlist management**: Agents can add/remove ONLY their own tickers
- **Removal criteria**: Time-based (minimum holding period) + performance-based (invalidation logic)
- Manual paper trade creation via API (not just agent ideas)
- Integration with existing daily update Celery task (21:30 UTC)

**Phase B (Full Engine - 2-3 weeks after vacation)**:
- Realistic fill simulation (slippage, bid/ask spread, liquidity constraints)
- Order types (market, limit, stop, stop-limit)
- Order states (pending, filled, partial, cancelled)
- Position sizing rules (equal weight, volatility-adjusted, Kelly criterion)
- Risk management (max position size 5%, correlation limits, sector concentration)
- Performance attribution (what worked, what failed, why?)
- Frontend visualization (P&L chart, trade log table, performance dashboard)

**Infrastructure Reuse**: 60-70% exists (idea_outcomes table, P&L calculation, exit logic, daily update task)

---

### Task 0060: CLI Agent Integration (UPDATED)

**Updates Made**:
- Added **Task 3.7**: Multi-Agent Collaboration Infrastructure (6 sub-tasks)
  - `agent_messages` table for inter-agent communication
  - `agent_workflows` table for orchestration state
  - Agent collaboration tools: `send_message_to_agent`, `query_agent_memory`, `vote_on_decision`
  - `WorkflowOrchestrator` service for multi-agent task assignment
  - Fallback/redundancy logic (if one agent fails, other continues)
  - Scheduled multi-agent workflows (daily gap analysis, paper trade validation)
- Added dependencies section linking to Tasks 0062, 0063, 0064
- Expanded summary to clarify multi-agent collaboration scope

**Multi-Agent Workflows Enabled**:
1. **Daily Gap Analysis**: Gemini agent → Claude agent → Consensus → Report generation → Git commit
2. **Paper Trade Validation**: Strategy agent → Risk agent → Consensus → Execution decision
3. **Research & Corroboration**: Agent A researches web → Agent B verifies sources → Consensus on data quality

---

### Task 0062: Gap Detection (UPDATED)

**Updates Made**:
- Added upstream dependency: Task 0060 Task 3.2a must complete first (unblocks Task 4.0 AI-powered gap analysis)
- Added related dependencies: Tasks 0063 (backtesting validates gap fills), 0064 (paper trading tests strategies)
- Phase 3 clarified: Only execute Task 4.0 AFTER Task 0060 completes (ai_analyzer must work via CLI first)

---

## Phased Execution Plan

### **Pre-Vacation MVP (1-2 weeks)** ← YOU ARE HERE

**Goal**: Functional autonomous system running during vacation

**Tasks**:
1. **Task 0063 Phase A** (Backtesting Quick MVP) - 3-5 days
   - Simple backtest engine functional
   - Agents can validate strategies historically
   - Results stored in database

2. **Task 0064 Phase A** (Paper Trading Quick MVP) - 3-5 days
   - Cash management working
   - Agents can create paper trades autonomously
   - Watchlist add/remove functional (agents only touch their own tickers)
   - Transaction log provides audit trail

3. **Task 0060 Task 3.7** (Multi-Agent Collaboration Minimal) - 2-3 days
   - `agent_messages` and `agent_workflows` tables created
   - Basic orchestration: Two agents can run in sequence
   - Shared context: Agents can query workflow state
   - Fallback: If one fails, other continues

**Outcome**: Before you leave for vacation, you have:
- ✅ Agents that can backtest strategies (simple but working)
- ✅ Agents that can create paper trades autonomously
- ✅ Agents that can add/remove watchlist tickers (with ownership tracking)
- ✅ Two agents (Gemini + Claude) that can collaborate on workflows
- ✅ Daily scheduled task that runs gap analysis → paper trade validation → commits to git
- ✅ Transaction log and audit trail for all autonomous actions

**Timeline**: 8-12 days (allow buffer for testing)

---

### **Post-Vacation Full System (6-8 weeks)**

**Phase 1: Complete Backtesting (3-4 weeks)**
- Task 0063 Phase B: Multi-symbol portfolio backtesting, walk-forward validation, optimization
- Integration with Task 0060: Agents use backtesting in decision-making
- Frontend visualization

**Phase 2: Complete Paper Trading (2-3 weeks)**
- Task 0064 Phase B: Realistic fills, order types, position sizing, risk management
- Performance attribution and analytics
- Frontend P&L dashboard

**Phase 3: Complete Multi-Agent Orchestration (1-2 weeks)**
- Task 0060 Task 3.7 full implementation: Advanced workflows, consensus mechanisms
- Scheduled autonomous workflows (daily, weekly)
- Web research integration (multi-source corroboration)

**Phase 4: Polish & Documentation (1 week)**
- End-to-end testing
- Documentation updates
- Performance tuning
- Monitoring and alerting

**Total Post-Vacation**: 7-10 weeks

---

## Recommended Execution Order

### Option A: **Parallel Quick MVP** (FASTEST - 10-12 days)

**Week 1**:
- Day 1-3: Task 0063 Phase A (Backtesting MVP) - can work independently
- Day 1-3: Task 0064 Phase A (Paper Trading MVP) - can work in parallel
- Day 4-5: Task 0060 Task 3.7 (Multi-Agent Minimal) - integrates above two

**Week 2**:
- Day 6-8: Integration testing (agents use backtesting + paper trading together)
- Day 9-10: Daily workflow setup (gap analysis → paper trading → git commits)
- Day 11-12: Manual testing, bug fixes, documentation

**Pros**: Fastest path to vacation-ready system
**Cons**: High parallel execution load (use `/do_it --max` to manage)

---

### Option B: **Sequential Stable MVP** (SAFER - 12-15 days)

**Week 1**:
- Day 1-5: Task 0063 Phase A (Backtesting MVP) - complete and test thoroughly
- Day 6-7: Integration test with existing agents

**Week 2**:
- Day 8-12: Task 0064 Phase A (Paper Trading MVP) - complete and test thoroughly
- Day 13-14: Integration test with backtesting

**Week 3**:
- Day 15-17: Task 0060 Task 3.7 (Multi-Agent Minimal) - orchestrate above
- Day 18-19: End-to-end workflow testing
- Day 20: Final polish, deploy, verify

**Pros**: Lower risk, each component fully tested before next
**Cons**: Takes 3 weeks (may miss vacation deadline)

---

### Option C: **Recommended Hybrid** (BALANCED - 11-14 days)

**Phase 1 (Days 1-5)**: Core Infrastructure
- Task 0063 Phase A (Backtesting) - Priority 1
- Task 0064 Phase A database schema + cash management - Priority 2 (partial parallel)

**Phase 2 (Days 6-9)**: Agent Integration
- Task 0064 Phase A agent tools + order execution (depends on database schema from Phase 1)
- Task 0060 Task 3.7.1-3.7.3 (tables + tools, no orchestration yet)

**Phase 3 (Days 10-12)**: Orchestration
- Task 0060 Task 3.7.4-3.7.6 (WorkflowOrchestrator + scheduled workflows)
- Integration testing (backtesting + paper trading + multi-agent)

**Phase 4 (Days 13-14)**: Validation & Deploy
- End-to-end workflow testing
- Git automation setup
- Final deployment and monitoring setup

**Pros**: Balances speed and stability, natural dependencies respected
**Cons**: Requires careful coordination (perfect for `/do_it --max`)

---

## User Requirements Mapping

| Your Requirement | Implementation | Task(s) | Phase |
|------------------|----------------|---------|-------|
| Multi-agent collaboration (Gemini + Claude) | WorkflowOrchestrator, agent_messages table | 0060 Task 3.7 | MVP |
| Daily gap analysis | Scheduled workflow: gap detection → consensus | 0060 Task 3.7.6 + 0062 | MVP |
| Paper trading | Order execution, cash management, P&L tracking | 0064 Phase A | MVP |
| Backtesting | Replay engine, performance metrics | 0063 Phase A | MVP |
| Autonomous watchlist management | add_ticker/remove_ticker tools, ownership tracking | 0064 Phase A | MVP |
| Only remove agent-added tickers | `added_by` field validation logic | 0064 Phase A | MVP |
| Web research + corroboration | Multi-agent workflow: research → verify → consensus | 0060 Task 3.7 + custom | Post-MVP |
| Git commits (regular) | Automated git workflow in scheduled tasks | 0060 Task 3.7.6 | MVP |
| Daily snapshot reports | WorkflowOrchestrator result storage + git commit | 0060 Task 3.7.6 | MVP |
| Strategy validation | Backtesting + paper trading integration | 0063 + 0064 | MVP |
| Remove tickers when invalidated | Time-based + performance-based removal criteria | 0064 Phase A | MVP |

**Coverage**: 100% of MVP requirements mapped ✅

---

## Risk Assessment

### High Risk Items

| Risk | Mitigation | Owner |
|------|------------|-------|
| **Vacation deadline (1-2 weeks)** | Option C (Hybrid) gives 11-14 days, allows 2-3 day buffer | User + Claude |
| **Agents make bad trades** | Paper trading only (no real money), transaction log audit trail, max position size 5% | Task 0064 Phase A |
| **Agents remove wrong tickers** | Ownership validation (can't remove user tickers), removal criteria (time + performance) | Task 0064 Phase A |
| **Multi-agent infinite loops** | Max workflow time limit, timeout on agent responses, fallback to single agent | Task 0060 Task 3.7.5 |
| **Data quality issues** | Web research requires multi-source corroboration (2-3 sources), confidence thresholds | Post-MVP |
| **Backtesting overfitting** | Walk-forward validation, out-of-sample testing | Task 0063 Phase B (post-MVP) |

### Medium Risk Items

| Risk | Mitigation | Owner |
|------|------------|-------|
| **CLI timeouts/hangs** | Timeout wrappers (300s), stderr capture, error logging | Task 0060 existing |
| **Database schema changes** | Migrations tested in dev, rollback plan | All tasks |
| **Integration complexity** | Phased approach, test each component independently first | Option C |
| **Git merge conflicts** | Automated commits with structured messages, regular pulls | Task 0060 Task 3.7.6 |

---

## Decision Points

Before proceeding, please confirm:

### 1. **Execution Option**

Which execution plan?
- **Option A**: Parallel Quick MVP (10-12 days, fastest)
- **Option B**: Sequential Stable MVP (15-20 days, safest)
- **Option C**: Recommended Hybrid (11-14 days, balanced) ← RECOMMENDED

**My recommendation**: Option C (Hybrid) - Respects dependencies, achieves vacation deadline with buffer, balanced risk/speed.

---

### 2. **Scope Confirmation**

**Pre-Vacation MVP Scope** (confirm each):
- ✅ Backtesting framework (simple single-symbol backtests)
- ✅ Paper trading engine (cash management, instant fills, audit trail)
- ✅ Autonomous watchlist management (agents add/remove tickers with ownership tracking)
- ✅ Multi-agent collaboration (two agents can run workflows together)
- ✅ Daily scheduled workflow (gap analysis → paper trades → git commit)
- ✅ Transaction log (audit trail for all autonomous actions)

**Deferred to Post-Vacation**:
- ⏸️ Advanced backtesting (walk-forward, optimization, portfolio-level)
- ⏸️ Realistic fills (slippage, liquidity, order types)
- ⏸️ Web research with multi-source corroboration
- ⏸️ Frontend visualization (equity curves, P&L charts)
- ⏸️ Advanced risk management (correlation limits, Kelly criterion)

**Confirm**: Is the MVP scope acceptable for vacation monitoring?

---

### 3. **Autonomous Behavior Limits**

**During Vacation MVP**:
- Agents can add tickers to watchlist (unlimited)
- Agents can remove ONLY tickers they added (not user tickers)
- Agents can create paper trades (default $100k cash, max 5% per position)
- Agents commit to git daily (structured commit messages)
- All actions logged to transaction log

**Guardrails**:
- No real money trades (paper trading only)
- Max position size: 5% of cash per trade
- Max holding period: 60 days
- Stop loss: 2x ATR (automatic)
- Workflow timeout: 1 hour max per workflow

**Confirm**: Are these limits acceptable? Want stricter/looser?

---

### 4. **Git Workflow**

**Proposed**:
- Daily commits to `main` branch (or dedicated `autonomous-trading` branch?)
- Commit message format: `[AUTONOMOUS] {date} - {workflow_type} - {result_summary}`
- Auto-push to remote after commit (or keep local only?)
- Snapshot files: `reports/autonomous/{YYYY-MM-DD}-gap-analysis.json`, `reports/autonomous/{YYYY-MM-DD}-paper-trades.json`

**Confirm**:
- Commit to main or separate branch?
- Auto-push to remote (so you can see in GitHub while on vacation)?
- Snapshot file format/location OK?

---

## Next Steps (Awaiting Your Confirmation)

Once you confirm the decisions above, I will:

1. **Update WORK_TRACKER.md** with new tasks (0063, 0064) and execution order
2. **Run `/do_it --max`** on Option C (Hybrid) execution plan
3. **Complete Pre-Vacation MVP** in 11-14 days:
   - Days 1-5: Backtesting MVP + database schema
   - Days 6-9: Paper trading agent tools + collaboration infrastructure
   - Days 10-12: Orchestration + workflows
   - Days 13-14: Testing + deployment
4. **Setup monitoring** so you can check status via GitHub commits while on vacation
5. **Provide handoff document** with system status, known limitations, and how to review results

---

## Questions for You

Please answer:

1. **Which execution option** (A, B, or C)?
2. **Confirm MVP scope** (acceptable for vacation)?
3. **Autonomous behavior limits** (acceptable or need adjustments)?
4. **Git workflow** (main vs branch, auto-push yes/no)?
5. **Vacation departure date** (so I know hard deadline)?
6. **Anything else** I missed or you want to add/change?

Once confirmed, I'm ready to execute with `/do_it --max`. Let's build this! 🚀

---

**Document Version**: 1.0
**Last Updated**: 2025-11-14
**Status**: Awaiting user confirmation
