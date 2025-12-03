# Task List: Multi-LLM Disagreement Detection

**Source**: VISION.md Gap Analysis via /align_it (2025-12-02)
**Complexity**: Complex
**Effort**: MEDIUM (2-3 days)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-02 12:15

---

## Summary

**Goal**: Fulfill VISION.md promise "Disagreement Detection: Flag when multiple LLMs disagree on recommendations" by implementing dual-reviewer execution (Claude AND Gemini), consensus logic, and user-facing disagreement dashboard.

**Approach**:
1. Implement dual-reviewer execution for each signal
2. Add consensus/voting logic for disagreements
3. Create user-facing disagreement alerts API
4. Add disagreement rate KPI tracking

**Scope Discovery**: Required to understand current strategy reviewer architecture

---

## Tasks

**IMPORTANT: Use section headers (###) for high-level tasks**

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Analyze current strategy reviewer
  - File: `backend/app/agents/strategy_reviewer.py`
  - Goal: Understand single-reviewer flow
  - Find: How reviews are stored, what fields exist
- [ ] 0.2 Review strategy_reviews table schema
  - Check: Current columns (provider, disagreement, etc.)
  - Find: How disagreement is currently detected
- [ ] 0.3 Analyze DualProviderClient
  - File: `backend/app/services/llm_client.py`
  - Goal: Understand existing dual-provider infrastructure
  - Find: How to execute both providers independently
- [ ] 0.4 Checkpoint: Confirm scope before proceeding
  - Current reviewer architecture: [TBD]
  - Storage format for dual reviews: [TBD]
  - Estimated effort: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Implement Dual-Reviewer Execution

- [ ] 1.1 Create MultiReviewer class
  - Execute Gemini review independently
  - Execute Claude review independently
  - Handle failures gracefully (one can fail, other continues)
- [ ] 1.2 Store both reviews in strategy_reviews table
  - Add `review_pair_id` to link dual reviews
  - Store separate rows for each provider's review
- [ ] 1.3 Create review comparison function
  - Compare sentiment/tone between reviews
  - Identify genuine disagreements (not just wording differences)
  - Return: agreement_score, disagreement_details
- [ ] 1.4 Update review_signal() to use dual execution
  - Call MultiReviewer instead of single reviewer
  - Return combined result with both reviews

### 2.0 Add Consensus/Voting Logic

- [ ] 2.1 Define disagreement criteria
  - Major disagreement: One says "bullish", other says "bearish"
  - Minor disagreement: Same direction but different concerns
  - Agreement: Both aligned on signal assessment
- [ ] 2.2 Implement consensus scoring
  - Agreement: Both reviews aligned → confidence HIGH
  - Minor disagreement: Flag but proceed → confidence MEDIUM
  - Major disagreement: Flag for user review → confidence LOW
- [ ] 2.3 Add disagreement severity to strategy_reviews
  - New column: `disagreement_severity` ENUM (none, minor, major)
  - Update on dual review completion
- [ ] 2.4 Create disagreement threshold configuration
  - Config: Major disagreement threshold (e.g., sentiment delta > 0.5)
  - Config: Auto-escalate to user review threshold

### 3.0 Create User-Facing Disagreement Dashboard

- [ ] 3.1 Create GET /api/disagreements endpoint
  - Query: Signals with major disagreements in last 7 days
  - Return: symbol, signal_type, gemini_review, claude_review, severity
- [ ] 3.2 Create GET /api/disagreements/stats endpoint
  - Return: Total reviews, agreement rate, disagreement rate
  - Return: Trend over last 30 days
- [ ] 3.3 Add disagreement alerts to watchlist API
  - Include `has_disagreement` flag in watchlist item response
  - Include `disagreement_summary` if present
- [ ] 3.4 Create frontend DisagreementAlert component
  - Show banner when LLM reviewers disagree
  - Display both perspectives side-by-side
  - Allow user to acknowledge/dismiss

### 4.0 Add Disagreement Rate KPI Tracking

- [ ] 4.1 Create Celery task for disagreement metrics
  - Calculate: Daily disagreement rate (%)
  - Calculate: Rolling 7-day average
  - Target: <20% disagreement rate per VISION.md
- [ ] 4.2 Store metrics in strategy_performance table
  - Add: `daily_disagreement_rate`, `weekly_avg_disagreement_rate`
- [ ] 4.3 Add to health dashboard
  - Show: Current disagreement rate
  - Alert: If rate exceeds 20% threshold
- [ ] 4.4 Schedule task in celery_schedules.py
  - Run: Daily at 23:00 UTC (after all reviews complete)

### 5.0 Integration and Testing

- [ ] 5.1 Write unit tests for MultiReviewer
  - Test: Both providers succeed
  - Test: One provider fails, other succeeds
  - Test: Both providers fail (graceful error)
- [ ] 5.2 Write unit tests for disagreement detection
  - Test: Major disagreement detected correctly
  - Test: Minor disagreement detected correctly
  - Test: Agreement detected correctly
- [ ] 5.3 Write integration test for full flow
  - Generate signal → Dual review → Store → Check disagreement
- [ ] 5.4 Update existing reviewer tests
  - Ensure backwards compatibility
- [ ] 5.5 Run full test suite
  - `cd ~/portfolio-ai/backend && pytest tests/ -v`
- [ ] 5.6 Restart services and verify
  - `bash ~/portfolio-ai/scripts/restart.sh`

---

## Verification

- [ ] Functional: Both LLMs review each signal
- [ ] Tests: 80%+ coverage on new code, all passing
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes
- [ ] API: GET /api/disagreements returns expected data
- [ ] KPI: Disagreement rate tracked and displayed on health dashboard
- [ ] Frontend: Disagreement alerts visible in watchlist
- [ ] Services: Restarted and verified
- [ ] Docs: AUTONOMOUS_TRADING.md updated with multi-reviewer flow
