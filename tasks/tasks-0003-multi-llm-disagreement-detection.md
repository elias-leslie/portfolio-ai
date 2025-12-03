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

- [x] 0.1 Analyze current strategy reviewer
  - File: `backend/app/agents/strategy_reviewer.py`
  - Finding: Single-provider with failover via `_generate_with_failover()`
  - Storage: One review per signal, `disagreement` = LLM vs rules (not provider vs provider)
- [x] 0.2 Review strategy_reviews table schema
  - Columns: id, watchlist_item_id, snapshot_id, symbol, review_text, provider, is_valid, disagreement, token_usage, created_at
  - Missing: review_pair_id, disagreement_severity
- [x] 0.3 Analyze DualProviderClient
  - File: `backend/app/agents/llm_client.py`
  - Finding: Sequential failover only, no parallel execution
  - Both providers accessible via `self.providers["gemini"]` and `self.providers["claude"]`
- [x] 0.4 Checkpoint: Scope confirmed
  - Current: Single review with failover
  - Need: Parallel dual execution, consensus logic, severity tracking
  - Estimated: 2-3 days as planned

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

### 1.0 Implement Dual-Reviewer Execution

- [x] 1.1 Create MultiReviewer class
  - File: `backend/app/agents/multi_reviewer.py`
  - Execute Gemini review independently (parallel asyncio.gather)
  - Execute Claude review independently
  - Handle failures gracefully (one can fail, other continues)
- [x] 1.2 Store both reviews in strategy_reviews table
  - Migration 056: Added review_pair_id, disagreement_severity, provider_disagreement, agreement_score
  - Store separate rows for each provider's review
- [x] 1.3 Create review comparison function
  - `_compute_consensus()`: Analyzes sentiment from keyword matching
  - `_analyze_sentiment()`: Scores -1.0 (bearish) to +1.0 (bullish)
  - Returns: agreement_score, disagreement_severity, provider_disagreement
- [x] 1.4 Update review_signal() endpoint to use dual execution
  - `POST /{item_id}/review?dual=true` (default)
  - Returns both reviews + consensus summary

### 2.0 Add Consensus/Voting Logic

- [x] 2.1 Define disagreement criteria (in `_compute_consensus()`)
  - Major disagreement: sentiment_diff >= 0.7 (one bullish, one bearish)
  - Minor disagreement: sentiment_diff 0.3-0.7 (same direction, different emphasis)
  - Agreement: sentiment_diff < 0.3
- [x] 2.2 Implement consensus scoring
  - agreement_score = 1.0 - (sentiment_diff / 2.0) → 0.0 to 1.0
  - DisagreementSeverity enum: NONE, MINOR, MAJOR
- [x] 2.3 Add disagreement severity to strategy_reviews
  - Migration 056: `disagreement_severity` column with CHECK constraint
  - Stored on dual review completion
- [x] 2.4 Threshold configuration (hardcoded for now)
  - Minor threshold: 0.3
  - Major threshold: 0.7
  - Can be made configurable later if needed

### 3.0 Create User-Facing Disagreement Dashboard

- [x] 3.1 Create GET /api/disagreements endpoint
  - File: `backend/app/api/disagreements.py`
  - Query: Signals with major disagreements in last N days
  - Return: symbol, gemini_review, claude_review, severity
- [x] 3.2 Create GET /api/disagreements/stats endpoint
  - Return: Total reviews, agreement rate, disagreement rate
  - Return: 7-day trend
- [x] 3.3 Create GET /api/disagreements/{symbol} endpoint
  - Return: All disagreements for specific symbol
- [x] 3.4 Create frontend components
  - DisagreementCard: Expandable card showing both reviews
  - DisagreementStatsCard: Stats with trend sparkline
  - DisagreementAlert: Dismissible banner for watchlist
  - Location: `frontend/components/disagreements/`

### 4.0 Add Disagreement Rate KPI Tracking

- [x] 4.1 Updated Celery task for disagreement metrics
  - File: `backend/app/tasks/strategy_metrics_tasks.py`
  - Existing task already tracked rules vs LLM disagreements
  - Added: provider_disagreements_count, provider_disagreement_rate_pct
  - Added: major/minor_disagreements_count, avg_agreement_score
- [x] 4.2 Store metrics in strategy_metrics table
  - Migration 057: Added 5 new columns
  - Daily collection includes all multi-LLM consensus metrics
- [x] 4.3 Dashboard endpoint available
  - GET /api/disagreements/stats returns rates and trend
  - Frontend DisagreementStatsCard shows target status
- [x] 4.4 Task already scheduled in celery_schedules.py
  - `strategy_metrics.daily_collection` runs daily

### 5.0 Integration and Testing

- [x] 5.1 Write unit tests for MultiReviewer
  - 14 tests in `tests/unit/test_multi_reviewer.py`
  - Tests: sentiment analysis, consensus computation, error handling
- [x] 5.2 Write unit tests for disagreement API
  - 5 tests in `tests/unit/test_disagreements_api.py`
  - Tests: list, stats, symbol endpoints
- [x] 5.3 Backwards compatibility
  - `POST /{item_id}/review?dual=false` still works for single provider
- [x] 5.4 Run full test suite
  - 493 unit tests passing (1 pre-existing failure unrelated to this task)
- [x] 5.5 Restart services and verify
  - All services running
  - API endpoints working: `/api/disagreements`, `/api/disagreements/stats`

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
