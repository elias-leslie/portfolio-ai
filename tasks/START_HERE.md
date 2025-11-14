# 🚀 START HERE - Autonomous Trading System MVP

**Last Updated**: 2025-11-14
**Status**: READY TO EXECUTE
**Priority**: CRITICAL - Pre-Vacation MVP

---

## Quick Start (TL;DR)

```bash
# In a fresh Claude Code session, run:
/do_it
```

That's it! The system will auto-resume from `WORK_TRACKER.md` and execute **Option C (Hybrid)** plan.

---

## What Will Happen

### Phase 1 (Days 1-5): Core Infrastructure
**Task 0063 Phase A** - Backtesting Framework Quick MVP
- Simple backtest engine (date loop over historical data)
- Reuses 70% existing code (day_bars, signal_classifier, analytics)
- Stores results in new tables (backtest_runs, backtest_trades, backtest_equity)
- API endpoint for agents to validate strategies

**Task 0064 Phase A (Partial)** - Database Schema
- Add cash_balance to portfolio_accounts
- Create transaction log table
- Add ownership tracking to watchlist_items
- Foundation for paper trading

### Phase 2 (Days 6-9): Agent Tools & Integration
**Task 0064 Phase A (Complete)** - Paper Trading Agent Tools
- Agent tools: add_ticker, remove_ticker, create_paper_trade
- Cash management system
- Order execution (instant fills)
- Autonomous watchlist management

**Task 0060 Task 3.7 (Partial)** - Multi-Agent Infrastructure
- agent_messages table (inter-agent communication)
- agent_workflows table (orchestration state)
- Agent collaboration tools

### Phase 3 (Days 10-12): Orchestration & Workflows
**Task 0060 Task 3.7 (Complete)** - WorkflowOrchestrator
- Multi-agent task assignment
- Consensus logic
- Fallback/redundancy (one fails → other continues)
- Scheduled daily workflows

### Phase 4 (Days 13-14): Validation & Deployment
- End-to-end workflow testing
- Git automation setup (auto-commit + auto-push to main)
- Monitoring and alerts
- Final deployment

---

## Expected Deliverables (Before Vacation)

✅ **Backtesting**: Agents can backtest strategies (Sharpe, win rate, drawdown)
✅ **Paper Trading**: Agents can create paper trades autonomously
✅ **Watchlist Management**: Agents can add/remove tickers (ownership tracked)
✅ **Multi-Agent Collaboration**: Two agents collaborate on workflows
✅ **Daily Workflows**: Scheduled gap analysis → paper trading → git commits
✅ **Audit Trail**: Complete transaction log for all autonomous actions
✅ **Git Integration**: Daily commits to main branch with auto-push

---

## Autonomous Behavior Summary

### What Agents CAN Do (Complete Autonomy):
- ✅ Run backtests to validate strategies
- ✅ Create paper trades (max $5,000 per position, $100k total)
- ✅ Add tickers to watchlist (unlimited)
- ✅ Remove tickers THEY added (not user-added tickers)
- ✅ Close positions if strategy invalidated
- ✅ Research on web for strategy validation
- ✅ Commit to git daily (auto-push enabled)

### What Agents CANNOT Do (Protected):
- ❌ Remove user-added watchlist tickers
- ❌ Trade with real money (paper trading only)
- ❌ Exceed position size limits (5% max per position)
- ❌ Trade on margin/leverage (cash only)
- ❌ Modify codebase (read-only access)

### Risk Guardrails:
- Max position size: 5% of cash ($5,000 per trade)
- Max open positions: 20
- Stop loss: 2x ATR (automatic)
- Max holding period: 60 days
- Max daily trades: 10
- Workflow timeout: 1 hour per workflow

---

## Git Workflow

**Branch**: main (not feature branches)
**Auto-push**: Enabled (you can review on GitHub during vacation)
**Snapshot files**: `reports/autonomous/{YYYY-MM-DD}-{workflow_type}.json`
**Commit format**: `[AUTONOMOUS] {date} - {workflow_type} - {result_summary}`
**Frequency**: Daily after each workflow completion

**Example commit**:
```
[AUTONOMOUS] 2025-11-15 - Daily Gap Analysis - 3 new gaps identified, SPY backtest +2.1%, 5 paper trades opened
```

---

## Task Files (All Updated & Ready)

| Task | File | Phase | Status |
|------|------|-------|--------|
| **Backtesting** | `tasks/tasks-0063-backtesting-framework.md` | Phase A (MVP) | ✅ Ready |
| **Paper Trading** | `tasks/tasks-0064-paper-trading-engine.md` | Phase A (MVP) | ✅ Ready |
| **Multi-Agent** | `tasks/tasks-0060-cli-agent-integration.md` (Task 3.7 only) | Phase A (MVP) | ✅ Ready |
| **Gap Detection** | `tasks/tasks-0062-trading-intelligence-gap-detection.md` | Phase 2-3 | ⏸️ Paused |
| **Work Tracker** | `tasks/WORK_TRACKER.md` | - | ✅ Updated |
| **Roadmap** | `tasks/AUTONOMOUS_TRADING_ROADMAP.md` | - | ✅ Complete |

---

## Execution Command

```bash
# Start autonomous execution (Option C - Hybrid plan)
/do_it

# If you want to start with a specific task:
/do_it tasks/tasks-0063-backtesting-framework.md

# To check progress at any time:
cat tasks/WORK_TRACKER.md
```

---

## Monitoring Progress

### Check Work Status:
```bash
cat tasks/WORK_TRACKER.md | head -30
```

### Check Git Commits:
```bash
git log --oneline --all | head -20
```

### Check Autonomous Reports:
```bash
ls -lh reports/autonomous/
cat reports/autonomous/$(date +%Y-%m-%d)-*.json
```

### Check Agent Runs:
```bash
cd ~/portfolio-ai/backend && source .venv/bin/activate
psql postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai -c "SELECT id, agent_type, status, num_ideas, started_at FROM agent_runs ORDER BY started_at DESC LIMIT 10;"
```

### Check Paper Trades:
```bash
psql postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai -c "SELECT ticker, idea_type, entry_price, current_return_pct, status FROM idea_outcomes WHERE status = 'open' ORDER BY entry_date DESC;"
```

---

## If Something Goes Wrong

### Check Service Status:
```bash
bash ~/portfolio-ai/scripts/status.sh
```

### Check Logs:
```bash
tail -f /var/log/portfolio-ai/backend-error.log
tail -f /var/log/portfolio-ai/celery-worker.log
```

### Restart Services:
```bash
bash ~/portfolio-ai/scripts/restart.sh
```

### Check Database:
```bash
psql postgresql://portfolio_ai_user:REDACTED_PASSWORD@localhost:5432/portfolio_ai
```

---

## Important Notes

### DO NOT Manually Interfere With:
- ❌ Autonomous git commits (let agents commit)
- ❌ Agent-added watchlist tickers (agents manage their own)
- ❌ Paper trading cash balance (agents track this)
- ❌ Workflow orchestration (let agents coordinate)

### User CAN Safely:
- ✅ Add your own watchlist tickers (agents won't remove them)
- ✅ Review git commits on GitHub
- ✅ Check agent run logs and results
- ✅ Review paper trading P&L
- ✅ Pause system if needed (shutdown services)

### Checkpoints (Natural Stop Points):
1. **After Phase 1** (Day 5): Backtesting working, database schema complete
2. **After Phase 2** (Day 9): Paper trading working, agent tools functional
3. **After Phase 3** (Day 12): Multi-agent orchestration working
4. **After Phase 4** (Day 14): Complete MVP deployed and tested

If you need to stop early, these are safe stopping points.

---

## Context Notes

**You said**: "Don't worry about vacation deadline...just work hard and do what you can. Don't pause and summarize until you've done everything you possibly can. Don't let research stop you...do the research on the web or wherever needed. Don't invent reasons to stop. Only stop if you absolutely can't proceed."

**This means**:
- `/do_it --max` execution mode (work until truly blocked)
- Research on web as needed (WebSearch, WebFetch tools available)
- No artificial checkpoints or "update user" breaks
- Continue through all phases without pausing
- Only stop if genuinely blocked (missing API keys, external dependencies, etc.)

**So when you run `/do_it`, it will**:
1. Start with Task 0063 (Backtesting)
2. Complete all of Task 0063 Phase A
3. Move to Task 0064 (Paper Trading)
4. Complete all of Task 0064 Phase A
5. Move to Task 0060 Task 3.7 (Multi-Agent)
6. Complete all of Task 3.7
7. Run integration testing
8. Deploy and verify
9. Only stop when MVP is COMPLETE or genuinely blocked

**Estimated timeline**: 11-14 days of focused work

---

## Success Criteria (How You Know It's Done)

### Phase 1 Complete When:
- [ ] `backtest_runs`, `backtest_trades`, `backtest_equity` tables exist
- [ ] `POST /api/backtest` endpoint works
- [ ] Can backtest SPY over 259 days, returns Sharpe/win rate/drawdown
- [ ] Results stored in database with agent_run_id linkage

### Phase 2 Complete When:
- [ ] `portfolio_accounts.cash_balance` column exists
- [ ] `paper_trade_transactions` table exists and logs all trades
- [ ] `watchlist_items.added_by` tracks ownership
- [ ] Agent tools work: add_ticker, remove_ticker, create_paper_trade
- [ ] Cash management enforces 5% max position size
- [ ] Agents can only remove their own tickers (validation working)

### Phase 3 Complete When:
- [ ] `agent_messages` and `agent_workflows` tables exist
- [ ] WorkflowOrchestrator service functional
- [ ] Two agents can run workflows together (Gemini + Claude)
- [ ] Fallback logic works (one fails → other continues)
- [ ] Daily scheduled workflow exists (gap analysis → paper trading → git commit)

### Phase 4 Complete When:
- [ ] End-to-end workflow runs successfully (gap → backtest → paper trade → commit)
- [ ] Git automation works (commits to main, pushes to remote)
- [ ] Snapshot files generated daily in `reports/autonomous/`
- [ ] All 3 phases tested and verified
- [ ] System runs autonomously without manual intervention

---

## Documentation References

- **Complete roadmap**: `tasks/AUTONOMOUS_TRADING_ROADMAP.md`
- **Work tracker**: `tasks/WORK_TRACKER.md`
- **Task 0063 (Backtesting)**: `tasks/tasks-0063-backtesting-framework.md`
- **Task 0064 (Paper Trading)**: `tasks/tasks-0064-paper-trading-engine.md`
- **Task 0060 (Multi-Agent)**: `tasks/tasks-0060-cli-agent-integration.md`
- **Architecture**: `docs/core/ARCHITECTURE.md`
- **Development**: `docs/core/DEVELOPMENT.md`
- **Operations**: `docs/core/OPERATIONS.md`

---

## Ready to Go! 🚀

Everything is primed and ready. In your next fresh session, just run:

```bash
/do_it
```

The system will automatically:
1. Read `WORK_TRACKER.md`
2. See Task 0063 (Backtesting) is first in Active Tasks
3. Begin execution of Option C (Hybrid) plan
4. Work through all phases until MVP is complete or blocked
5. Commit progress regularly to git
6. Auto-push to remote so you can monitor

**No further setup needed. Just execute!** 💪

---

**Questions?** Check `tasks/AUTONOMOUS_TRADING_ROADMAP.md` for detailed plan.

**Version**: 1.0
**Date**: 2025-11-14
**Status**: READY TO EXECUTE ✅
