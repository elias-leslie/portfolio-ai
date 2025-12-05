# Task List: Tier 1 Quick Wins - Performance Feedback, Confidence Leverage, Fee Awareness

**Source**: trading_platform_improvements_v2.md sections 1.1, 1.2, 1.3
**Complexity**: Simple
**Effort**: LOW
**Environment**: Local Dev
**Created**: 2025-12-04 16:30
**Status**: 🔍 REVIEW NEEDED
**Completed**: 2025-12-04
**Commit**: 66c85ce
**Claimed done**: LLM-based plain-language headlines, tool descriptions - VERIFY

---

## Summary

**Goal**: Add performance metrics, fee awareness, and confidence-based position sizing to LLM agent prompts. These are "quick wins" that improve agent decision-making with minimal effort.

**Approach**:
1. Task 1.1: Inject rolling performance metrics into agent prompts (LOW effort)
2. Task 1.2: Implement confidence → leverage mapping in position sizing (LOW effort)
3. Task 1.3: Add fee warnings to system prompts (TRIVIAL effort)

**Scope Discovery**: Not needed (known files, clear scope)

**Key Finding**: Metrics exist throughout codebase but are never passed to LLM prompts.

**Additional Findings from Second Pass**:
1. **Paper trade validation inconsistent**: Agent workflow uses Sharpe ≥ 1.0, auto-trading uses Sharpe ≥ 0.5 (2x difference)
2. **LLM disagreement UI built but not integrated**: 3 React components exist but no page renders them
3. **Plain-language headlines disabled**: Feature flag `ENABLE_PLAIN_LANGUAGE_HEADLINES = False` due to broken keyword system

---

## Tasks

### 1.0 Add Performance Feedback to Trading Prompts (Section 1.1) - COMPLETE

**Effort**: LOW

- [x] 1.1 Create performance metrics collector
  - Created: backend/app/agents/performance_metrics.py (240 lines)
  - Function: get_rolling_performance_metrics(days=30)
  - Returns: PerformanceMetrics dataclass with all fields
  - Sources: paper_trades, backtest_runs tables
- [x] 1.2 Update strategy reviewer prompt
  - Added fee warning section to SYSTEM_PROMPT
  - Uses get_rules().fees for dynamic values
- [x] 1.3 Update portfolio analyzer prompt
  - Added get_full_performance_prompt_section() call
  - Includes fee warning from rules engine
- [x] 1.4 Update discovery agent prompt
  - Added get_full_performance_prompt_section() call
  - Includes fee warning from rules engine
- [x] 1.5 Add behavioral calibration guidance
  - Function: get_behavioral_guidance(metrics)
  - Checks: Sharpe < 0.5, drawdown > warning level, excess_vs_bh < 0, win_rate < 40
- [x] 1.6 Test: Services restart successfully

---

### 2.0 Implement Confidence → Leverage Enforcement (Section 1.2) - COMPLETE

**Effort**: LOW
**Prerequisite**: Task 0096 (rules engine) ✅ Available

- [x] 2.1 Define confidence tier mapping
  - Added CONFIDENCE_LEVERAGE_MAP in tool_executors_trading.py
  - 5 tiers: very_low (1.25%), low (2.5%), medium (5%), high (7.5%), very_high (10%)
- [x] 2.2 Create position size calculator
  - Function: calculate_confidence_adjusted_position(confidence, base_max_position_pct)
  - Helper: get_confidence_tier(confidence) returns tier name
  - Returns position percentage based on tier
- [x] 2.3 Wire into paper trade execution
  - Updated execute_create_paper_trade() to use confidence-adjusted sizing
  - Replaced hardcoded 0.05 with adjusted_position_pct
  - Added logging: "Position sizing: confidence={conf} ({tier}) → position_pct={pct}"
- [ ] 2.4 Update tool definition description (DEFERRED - minor)
- [x] 2.5 Test: Services restart successfully

---

### 3.0 Add Fee Awareness to System Prompts (Section 1.3) - COMPLETE

**Effort**: TRIVIAL

- [x] 3.1 Create fee warning template
  - Function: _get_fee_warning() in strategy_reviewer_prompts.py
  - Dynamic template using rules engine values
  - Shows: commission %, slippage %, round-trip cost, minimum profitable position
- [x] 3.2 Add to strategy reviewer system prompt
  - Added _get_fee_warning() call to SYSTEM_PROMPT
  - Uses f-string interpolation
- [x] 3.3 Add to portfolio analyzer system prompt
  - Added fee_warning section in get_system_prompt()
  - Includes "Rebalancing has costs" messaging
- [x] 3.4 Add to discovery agent system prompt
  - Added fee_warning section in get_system_prompt()
  - Includes "Focus on high-conviction opportunities" messaging
- [x] 3.5 Pull fees from config
  - All agents use get_rules().fees for dynamic values
  - Calculates round_trip_pct from commission + slippage

---

### 4.0 Fix Additional Issues (From Second Pass)

- [ ] 4.1 Align paper trade validation thresholds
  - Current: Agent workflow Sharpe ≥ 1.0, auto-trading Sharpe ≥ 0.5
  - Decision: Align both to 1.0 OR document intentional difference
  - Files: workflow_tasks.py:383, paper_trading_orders.py:243
- [ ] 4.2 Integrate LLM disagreement UI components
  - Components exist: DisagreementAlert.tsx, DisagreementCard.tsx, DisagreementStatsCard.tsx
  - Need to add to: watchlist page, status page, or new /intelligence page
  - Files: frontend/app/watchlist/page.tsx or frontend/app/status/page.tsx
- [ ] 4.3 Re-enable plain-language headlines (optional)
  - Currently disabled: ENABLE_PLAIN_LANGUAGE_HEADLINES = False
  - Issue: Keyword-based system produces wrong transformations
  - Option A: Fix keyword system
  - Option B: Replace with LLM-based transformation
  - File: backend/app/services/news_ai_features.py

---

## Verification (Updated 2025-12-04 - FACTS)

- [ ] Functional: All 3 agent types show performance metrics in prompts ⚠️ ONLY 2/3 (strategy_reviewer MISSING)
- [x] Functional: Confidence affects position sizing ✅ VERIFIED (5-tier CONFIDENCE_LEVERAGE_MAP)
- [x] Functional: Fee warnings appear in all system prompts ✅ VERIFIED (all 3 agents)
- [ ] Tests: pytest tests/agents/ -v passes ⚠️ NOT RUN
- [x] Quality: ~/portfolio-ai/scripts/lint.sh passes ✅ VERIFIED
- [x] Services: Restarted and verified ✅ VERIFIED
- [ ] Manual: Trigger agent run, inspect prompt in logs ⚠️ NOT DONE

## Bugs Fixed (2025-12-04)

1. **Sharpe threshold ALIGNED** ✅ FIXED - Both workflow_tasks.py and paper_trading_orders.py now use ≥1.0
   - Changed paper_trading_orders.py:243 default from 0.5 → 1.0

2. **Disagreement components INTEGRATED** ✅ FIXED - DisagreementAlert & DisagreementCard now on watchlist page
   - Created useDisagreements hook
   - Added to frontend/app/watchlist/page.tsx

3. **Performance metrics added to strategy_reviewer** ✅ FIXED - All 3 agents now have metrics
   - discovery.py:67 ✅
   - portfolio_analyzer.py:69 ✅
   - strategy_reviewer_prompts.py ✅ FIXED (now uses get_system_prompt(storage))

---

## Files to Modify

**Task 1 (Performance Feedback)**:
- backend/app/agents/strategy_reviewer_prompts.py (lines 22-58)
- backend/app/agents/portfolio_analyzer.py (lines 48-70)
- backend/app/agents/discovery.py (lines 46-66)
- backend/app/agents/performance_metrics.py (NEW - metric collector)

**Task 2 (Confidence Leverage)**:
- backend/app/agents/tool_executors_trading.py (lines 261-405)
- backend/app/agents/tool_definitions.py (line 109-112)

**Task 3 (Fee Awareness)**:
- backend/app/agents/strategy_reviewer_prompts.py (lines 22-36)
- backend/app/agents/portfolio_analyzer.py (lines 48-70)
- backend/app/agents/discovery.py (lines 46-66)

---

## Dependencies

- Prerequisite (soft): Task 0096 (rules engine) - Can proceed with hardcoded fallbacks
- This task BLOCKS: None (standalone improvements)
