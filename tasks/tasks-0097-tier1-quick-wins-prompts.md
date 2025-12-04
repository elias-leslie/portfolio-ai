# Task List: Tier 1 Quick Wins - Performance Feedback, Confidence Leverage, Fee Awareness

**Source**: trading_platform_improvements_v2.md sections 1.1, 1.2, 1.3
**Complexity**: Simple
**Effort**: LOW
**Environment**: Local Dev
**Created**: 2025-12-04 16:30

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

### 1.0 Add Performance Feedback to Trading Prompts (Section 1.1)

**Effort**: LOW

- [ ] 1.1 Create performance metrics collector
  - New function: get_rolling_performance_metrics(days=30)
  - Returns: session_return_pct, rolling_sharpe, win_rate, current_drawdown, excess_vs_bh
  - Source data from: paper_trades, backtest_runs tables
- [ ] 1.2 Update strategy reviewer prompt
  - Edit strategy_reviewer_prompts.py REVIEW_PROMPT_TEMPLATE
  - Add performance metrics section before analysis request
  - Format: "YOUR PERFORMANCE METRICS:\n- Session Return: {return_pct}%..."
- [ ] 1.3 Update portfolio analyzer prompt
  - Edit portfolio_analyzer.py get_system_prompt()
  - Include performance context for risk calibration
- [ ] 1.4 Update discovery agent prompt
  - Edit discovery.py get_system_prompt()
  - Add performance awareness for idea generation confidence
- [ ] 1.5 Add behavioral calibration guidance
  - If Sharpe < 0.5: "Consider reducing position sizes"
  - If drawdown > 15%: "Be more conservative, tighten stops"
  - If excess_vs_bh < 0: "Question if active trading adds value"
- [ ] 1.6 Test prompt updates
  - Verify metrics appear in LLM calls
  - Check agent behavior changes with different metric values

---

### 2.0 Implement Confidence → Leverage Enforcement (Section 1.2)

**Effort**: LOW
**Prerequisite**: Task 0096 (rules engine) OR hardcode temporarily

- [ ] 2.1 Define confidence tier mapping
  - If rules engine exists: Use get_rules().position_sizing.confidence_leverage_map
  - Fallback: Define inline mapping in tool_executors_trading.py
  ```python
  CONFIDENCE_LEVERAGE_MAP = {
      "low": {"min": 0.0, "max": 0.3, "multiplier": 0.5},
      "medium": {"min": 0.3, "max": 0.6, "multiplier": 1.0},
      "high": {"min": 0.6, "max": 0.8, "multiplier": 1.5},
      "very_high": {"min": 0.8, "max": 1.0, "multiplier": 2.0},
  }
  ```
- [ ] 2.2 Create position size calculator
  - New function: calculate_confidence_adjusted_size(confidence, base_size)
  - Look up tier from confidence score
  - Return: base_size * tier_multiplier
- [ ] 2.3 Wire into paper trade execution
  - Edit tool_executors_trading.py execute_create_paper_trade()
  - Replace hardcoded `max_position_pct=0.05` with confidence-adjusted value
  - Log: "Position sized at {pct}% due to confidence {conf}"
- [ ] 2.4 Update tool definition description
  - Edit tool_definitions.py confidence_score description
  - Clarify: "Used to scale position size - higher confidence = larger position"
- [ ] 2.5 Test confidence enforcement
  - Low confidence (0.2) → smaller position
  - High confidence (0.9) → larger position
  - Verify in paper_trades table

---

### 3.0 Add Fee Awareness to System Prompts (Section 1.3)

**Effort**: TRIVIAL

- [ ] 3.1 Create fee warning template
  ```
  TRADING COSTS:
  - Commission: 0.05% per trade
  - Slippage: ~0.1% on market orders
  - Minimum profitable position: $500
  - Round-trip cost: ~0.3%

  Excessive trading erodes returns. GPT-5 and Gemini lost 50%+
  in Alpha Arena primarily from fee erosion.
  ```
- [ ] 3.2 Add to strategy reviewer system prompt
  - Edit strategy_reviewer_prompts.py SYSTEM_PROMPT
  - Include fee warning section
- [ ] 3.3 Add to portfolio analyzer system prompt
  - Edit portfolio_analyzer.py get_system_prompt()
  - Include fee warning section
- [ ] 3.4 Add to discovery agent system prompt
  - Edit discovery.py get_system_prompt()
  - Include fee warning section
- [ ] 3.5 Pull fees from config (if rules engine available)
  - Replace hardcoded values with get_rules().fees
  - Format dynamically: f"Commission: {rules.fees.commission_pct * 100}%"

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

## Verification

- [ ] Functional: All 3 agent types show performance metrics in prompts
- [ ] Functional: Confidence affects position sizing
- [ ] Functional: Fee warnings appear in all system prompts
- [ ] Tests: pytest tests/agents/ -v passes
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes
- [ ] Services: Restarted and verified
- [ ] Manual: Trigger agent run, inspect prompt in logs

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
