# Execution Plan: Option 2 (Partial Parallel)

**Goal**: Complete tasks 0058a, 0060, and 0062 with optimal parallelization and zero conflicts

**Total Time**: ~22-28 hours (vs 26-33 sequential) - **20% faster**

---

## Phase 1: Fix Existing Features (P0 Critical)

**Time**: 4-8 hours
**Run**: Sequential (independent task)

```bash
/do_it --max tasks/tasks-0058a-fix-existing-features.md
```

**What this does**:
- Fixes real-time data pipeline (Fear & Greed shows TODAY's data)
- Fixes watchlist score breakdown (Valuation/Growth/Health/Sentiment)
- Populates all 5 Fear & Greed components (VIX, SPY, RSI, HY spread, breadth)
- Parses valuation data (P/E, P/B, P/S ratios)

**Verification**:
- Dashboard shows "As of 4:00 PM ET today" (not "3 days old")
- Watchlist breakdown shows numeric values (not N/A)
- All Fear & Greed components populated

**Ready for Phase 2**: ✅ When all tasks complete, services restarted, verification passed

---

## Phase 2: Parallel Execution (0060 + 0062)

**Time**: 12-18 hours (both run simultaneously)
**Run**: Parallel (0% file overlap, coordinated DB migrations + service restarts)

```bash
/do_it --max tasks/tasks-0060-cli-agent-integration.md tasks/tasks-0062-trading-intelligence-gap-detection.md
```

**What this does**:

### Task 0060 (CLI Agent Integration):
- Scope discovery (find all Anthropic references)
- Design provider-agnostic runtime
- Build Gemini CLI + Claude Code CLI adapters
- **Refactor ai_analyzer.py to use CLI** (Task 3.2a - HIGH PRIORITY)
- Refactor Agent base class
- Build agent UI (dock + /agents page)
- Testing and verification

### Task 0062 (Gap Detection) - **SKIP Task 4.0**:
- ✅ Task 3.3-3.6: Frontend UI (GapsList, drill-down, task generation, watchlist coverage)
- ✅ Task 5: Integration with trading workflows
- ✅ Task 6: Scheduled gap analysis & monitoring
- ✅ Task 7: Documentation & examples
- ✅ Task 8.1-8.4: Testing (skip 8.5 - AI testing)
- ✅ Task 9: Baseline & production deployment
- ⏸️ **SKIP Task 4.0**: AI-powered gap analysis (DEFERRED to Phase 3)

**Critical**: Agent will see `[DEFERRED]` markers and skip Task 4.0 automatically

**Coordination**:
- Database migrations: Run sequentially (agent coordinates)
- Service restarts: Once at end (agent coordinates)
- No file conflicts: 0% overlap verified

**Verification**:
- Task 0060: All agents use CLI (zero Anthropic calls), UI functional
- Task 0062: Gap detection works (manual recommendations only, AI skipped)

**Ready for Phase 3**: ✅ When Task 0060 100% complete (especially Task 3.2a)

---

## Phase 3: Complete AI Gap Analysis

**Time**: 2-3 hours
**Run**: Manual (complete deferred Task 4.0)

**Prerequisites**:
1. ✅ Task 0060 Task 3.2a complete (ai_analyzer.py uses CLI)
2. ✅ Test ai_analyzer manually: `claude -p --output-format stream-json`
3. ✅ Verify zero Anthropic API calls

**Execute**:
```bash
# Option A: Run /do_it on 0062 again (will only do Task 4.0 + 8.5)
/do_it tasks/tasks-0062-trading-intelligence-gap-detection.md

# Option B: Manual execution
# Read Phase 3 section in tasks-0062 and complete tasks manually
```

**What this does**:
- Task 4.1: Add gap analysis to capabilities AI insights
- Task 4.2: Generate actionable recommendations
- Task 4.3: Create gap insights in database
- Task 4.4: Add "Ask AI" feature for gaps
- Task 8.5: Test AI-powered gap analysis

**Verification**:
- AI insights identify real gaps (not false positives)
- Recommendations practical and prioritized correctly
- Confidence scores make sense

**Completion**:
- [ ] All Task 4.0 sub-tasks complete
- [ ] Task 8.5 complete
- [ ] AI verification items checked
- [ ] Update WORK_TRACKER.md: Mark Task 0062 as 100% complete
- [ ] Final commit: "feat: complete AI-powered gap analysis (Task 0062 Phase 3)"

---

## Summary

**Phase 1**: tasks-0058a (fix P0 issues) → **4-8 hours**
**Phase 2**: tasks-0060 + tasks-0062 (parallel) → **12-18 hours**
**Phase 3**: tasks-0062 Task 4.0 (AI features) → **2-3 hours**

**Total**: **18-29 hours** (aggressive parallelization, safe coordination)

**Benefits**:
- ✅ 20% faster than sequential
- ✅ Zero file conflicts (verified)
- ✅ Clear phase boundaries
- ✅ P0 fixes delivered first
- ✅ Safe fallback (skip Phase 3 if needed)

**Ready to Execute**: Copy commands from each phase and run when ready!
