# Strategy Seed Pipeline

**Implements**: FEAT-218
**Status**: complete
**Effort**: MEDIUM
**Priority**: P1

## Context
Discovery Agent currently stores "ideas" with `symbol: null` (broken). This feature merges Ideas into the Strategy system with evolution tracking. Seeds from AI agents trigger the existing `strategy_research_workflow()` which includes walk-forward backtesting. Users see the full evolution: Seed -> Backtest -> Strategy -> Signals -> Trades -> Performance.

**Key Integration**: Uses EXISTING `strategy_research_workflow.py` - NO new backtest logic needed.

## 0.0 Scope Discovery (MANDATORY)
- [x] Run 2-3 "very thorough" Explore agents on:
  - Discovery Agent output format (`backend/app/agents/discovery.py`)
  - Strategy workflow (`backend/app/agents/workflows/strategy_research_workflow.py`)
  - Agent tools (`backend/app/agents/tools.py` - store_idea)
  - Strategy definitions schema
- [x] Document all files to modify with line ranges
- [x] Identify similar patterns in codebase
- [x] Note edge cases and dependencies

## Files to Modify
[Populated after scope discovery]

| Area | Files | Changes |
|------|-------|---------|
| **Agent Output** | `backend/app/agents/discovery.py` | Output "strategy_seed" instead of "idea" |
| **Storage** | `backend/app/agents/tools.py` | `store_strategy_seed()` replaces `store_idea()` |
| **Trigger** | `backend/app/tasks/agent_tasks.py` | After seed stored, trigger strategy workflow if confidence >= 7 |
| **DB Schema** | `backend/migrations/XXX_strategy_seed_columns.sql` | Add `seed_id`, `seed_thesis`, `seed_confidence` to strategy_definitions |
| **API** | `backend/app/api/routes/strategies.py` | Add `/api/strategy-seeds/` endpoint |
| **UI** | `frontend/app/strategies/page.tsx` | Show seed origin, evolution timeline |
| **UI Components** | `frontend/components/strategies/SeedEvolution.tsx` (NEW) | Timeline visualization |
| **Deprecate** | `agent_ideas` table, `/api/ideas/` endpoints | Mark deprecated, migrate existing data |

## Steps

### seed-001-schema: Add Seed Columns to strategy_definitions (LOW)
**What**: Add `seed_id`, `seed_thesis`, `seed_confidence` columns to strategy_definitions table
**Why**: Link strategies back to their originating seed for evolution tracking
**How**:
- Create migration adding nullable columns
- seed_id: UUID reference to the seed that triggered this strategy
- seed_thesis: Original AI thesis (preserved even after strategy evolution)
- seed_confidence: Original confidence score (1-10)
**Files**: `backend/migrations/XXX_strategy_seed_columns.sql`
**Verification**: `psql -c "\d strategy_definitions"` shows new columns

### seed-002-agent-output: Modify Discovery Agent Output (MEDIUM)
**What**: Discovery Agent outputs strategy seeds with symbol, thesis, confidence
**Why**: Fix the broken Ideas system (currently stores `symbol: null`)
**How**:
- Modify Discovery Agent to use `store_strategy_seed()` tool
- Ensure symbol is ALWAYS populated (required field validation)
- Include thesis (AI reasoning) and confidence (1-10 scale)
**Files**:
- `backend/app/agents/discovery.py`
- `backend/app/agents/tools.py` - new `store_strategy_seed()` function
**Verification**: New seeds have non-null symbol, thesis, confidence

### seed-003-trigger: Auto-trigger Strategy Workflow (MEDIUM)
**What**: High-confidence seeds (>=7/10) automatically trigger `strategy_research_workflow()`
**Why**: Connect AI output to action - seeds shouldn't be dead-end
**How**:
- In `store_strategy_seed()`, check confidence level
- If confidence >= 7, call `strategy_research_workflow.apply_async()`
- Workflow includes: research aggregation, strategy generation, walk-forward backtest
**Files**:
- `backend/app/agents/tools.py`
- `backend/app/tasks/agent_tasks.py`
**Verification**: Celery logs show `strategy_research_workflow` triggered after high-confidence seed

### seed-004-ui-evolution: Show Evolution on Strategies Page (MEDIUM)
**What**: Display seed -> backtest -> strategy -> signals -> trades -> performance timeline
**Why**: Users see the full AI reasoning journey, builds trust
**How**:
- Create `SeedEvolution.tsx` component showing timeline
- Add "Origin" section to strategy detail showing seed thesis/confidence
- Show backtest results inline with evolution
**Files**:
- `frontend/components/strategies/SeedEvolution.tsx` (NEW)
- `frontend/app/strategies/page.tsx`
- `frontend/components/strategies/StrategyDetail.tsx`
**Verification**: Screenshot shows evolution timeline for strategy with seed origin

### seed-005-deprecate-ideas: Deprecate Ideas System (LOW)
**What**: Mark agent_ideas table and /api/ideas/ endpoints as deprecated
**Why**: Ideas merged into Strategy system - no separate tracking needed
**How**:
- Add deprecation notice to /api/ideas/ endpoints (return warning header)
- Migrate any valuable existing ideas to seeds (likely none - all have symbol=null)
- Update FEAT-051 to deprecated status
- DO NOT delete table yet - leave for rollback safety
**Files**:
- `backend/app/api/routes/ideas.py`
- Update FEAT-051 status
**Verification**: /api/ideas/ returns deprecation warning, FEAT-051 marked deprecated

## Verification
- [x] ac-001: `curl -s http://localhost:8000/api/strategy-seeds/ | jq` returns seeds list (empty until Discovery Agent runs)
- [x] ac-002: trigger_strategy_from_seed Celery task created, auto-triggers for confidence >= 7
- [x] ac-003: SeedEvolution component added to StrategyDetailModal showing evolution timeline
- [x] ac-004: `psql -c "SELECT column_name FROM information_schema.columns WHERE table_name='strategy_definitions' AND column_name LIKE 'seed_%'"` shows seed_id, seed_thesis, seed_confidence columns

## Rollback
If issues occur: `git reset --hard HEAD~1`

## Dependencies
- EXISTING: `strategy_research_workflow.py` (walk-forward backtest)
- EXISTING: `strategy_monitoring_tasks.py` (70% Sharpe threshold for activation)
- DEPRECATES: FEAT-051 (Ideas/Catalysts View)
