<!-- PAUSED: 2025-11-14 17:30 | Context: 86% | Next: Task 6 backend fixes (ConnectionManager API) -->

# Task List: Trading Intelligence Gap Detection

**Source**: User request via /task_it
**Complexity**: Complex
**Effort**: HIGH (15-20 hours)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-13 23:45
**Status**: PAUSED
**PAUSED**: 2025-11-14 17:30 (Context limit 86% + type errors in backend)
**Next**: Task 6 - Fix gap_analysis_tasks.py type errors (ConnectionManager.connection() API, GapAnalysisResult TypedDict keys)

**Dependencies (Upstream)**:
- **Task 0060** (CLI Agent Integration): Task 3.2a must complete to unblock Task 4.0 here (AI-powered gap analysis requires working ai_analyzer)

**Dependencies (Related)**:
- **Task 0063** (Backtesting Framework): Validates gap-fill effectiveness - strategies work better after gaps filled?
- **Task 0064** (Paper Trading Engine): Tests strategies in real-time - gap fills improve paper trading results?

**Execution Plan** (Option 2 - Partial Parallel):
- **Phase 1**: Complete tasks-0058a (fix existing features) - 4-8 hours
- **Phase 2**: Run THIS task in parallel with tasks-0060, BUT skip Task 4.0 (deferred)
  - Complete: Tasks 3.3-3.6, 5.0-9.0 (no blockers)
  - Skip: Task 4.0 (DEFERRED - requires ai_analyzer working from 0060 Task 3.2a)
- **Phase 3**: After 0060 completes, return and complete Task 4.0

---

## Summary

**Goal**: Build gap detection system that identifies missing data capabilities needed for profitable trading strategies. Primary purpose: Help AI trading agent (Claude) detect what data it's missing to provide true edge and successful trading insights. Extend existing capabilities feature with trading-focused gap analysis.

**Approach**:
- Define comprehensive trading analysis requirements (technical, fundamental, sentiment, risk)
- Build gap detector that compares REQUIRED vs AVAILABLE data per analysis type
- Show system-wide gaps, per-analysis coverage, and watchlist coverage
- Enable workflow: AI flags gaps → provides recommendations → user approves → AI builds task list to fill gaps
- Integrate with existing capabilities system (Task 0061) since it already has the data

**Scope Discovery**: Required (understand existing capabilities structure, data models, and trading data available)

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [x] 0.1 Run Explore subagent in "medium" mode
  - ✅ COMPLETED: Comprehensive gap analysis conducted
  - ✅ Identified 47 gaps across 8 categories (Market Data, Fundamentals, Signals, Risk, Execution, Macro, ML, Compliance)
  - ✅ Found: 17 P0 (critical), 20 P1 (high), 7 P2 (medium), 3 P3 (low)
- [x] 0.2 Document findings and update task list
  - ✅ COMPLETED: Created `/home/kasadis/portfolio-ai/gap_definition.md`
  - ✅ Listed all 47 gaps with: Current state, Desired state, Impact, Data sources, Effort, Code refs
  - ✅ Defined TOP 10 priority gaps (Impact × 1/Effort ranking)
  - ✅ Created 4-week Minimum Viable Gap-Fill roadmap
- [x] 0.3 Review gap_definition.md before proceeding
  - ✅ **Current system**: Limited swing trading only (~30% confidence)
  - ✅ **Critical findings**: Portfolio risk math wrong, position sizing broken, signals are noise
  - ✅ **Minimum viable**: 12 P0 gaps (4 weeks) → Sharpe 1.2-1.8
  - ✅ **Full edge**: P0+P1 gaps (12-16 weeks) → Sharpe >2.0
- [x] 0.4 Reference gap_definition.md throughout implementation
  - ✅ Use as source of truth for requirements, priorities, data sources
  - ✅ Gap IDs: GAP-001 through GAP-053 documented
  - ✅ **KEY**: Backtesting framework (GAP-019) identified as prerequisite for validating gap fills

**SCOPE CONFIRMED - PROCEEDING WITH IMPLEMENTATION**

---

### 1.0 Define Trading Analysis Requirements Framework

- [x] 1.1 Create analysis requirements taxonomy
  - Define what data each analysis type needs (comprehensive, market wizard level)
  - **Technical Analysis**: OHLCV, volume, technical indicators, chart patterns, support/resistance, multi-timeframe
  - **Fundamental Analysis**: Earnings, revenue, margins, cash flow, P/E, P/B, PEG, growth rates, guidance, quality scores
  - **Sentiment Analysis**: News sentiment, analyst ratings, options flow (put/call), social sentiment, insider trading
  - **Risk Analysis**: Volatility, beta, correlation, Sharpe ratio, max drawdown, VaR/CVaR, position sizing, covariance matrix
  - **Macro Analysis**: Fed policy, rates, inflation, sector rotation, economic indicators, yield curve, credit spreads
  - **Event Analysis**: Earnings dates, ex-dividend dates, splits, M&A, regulatory events, earnings surprises
  - **Execution Quality Analysis**: Bid/ask spreads, slippage, market impact, liquidity (ADV), fill quality *(NEW - gap_definition.md)*
  - **Cross-Asset Analysis**: FX correlations, commodity correlations, bond yields, sector rotation, crypto *(NEW - gap_definition.md)*
  - **Alternative Data Analysis**: Credit card, app analytics, web traffic, satellite, job postings *(NEW - gap_definition.md)*
  - **Market Microstructure Analysis**: Level 2 order book, time & sales, NBBO, VWAP, spread volatility *(NEW - gap_definition.md)*
  - **ML Model Analysis**: Feature engineering, backtesting, model validation, performance tracking *(NEW - gap_definition.md)*
- [x] 1.2 Create requirements configuration file
  - ✅ Created `backend/app/config/trading_requirements.yaml` (891 lines)
  - ✅ Structure: analysis_type → required/recommended/optional → capabilities
  - ✅ All 47 gaps mapped with criticality (P0/P1/P2/P3)
  - ✅ Freshness requirements specified per capability
  - ✅ Coverage requirements specified per capability
  - ✅ Data sources documented per capability
  - ✅ 12 analysis types: Technical, Fundamental, Sentiment, Risk, Execution, Macro, ML, Compliance
- [x] 1.3 Define data capability maturity levels
  - ✅ Level 0: Missing (0% coverage, can't perform analysis)
  - ✅ Level 1: Minimal (1-40% coverage, limited insights)
  - ✅ Level 2: Adequate (41-80% coverage, reasonable insights)
  - ✅ Level 3: Complete (81-100% coverage, strong edge potential)
  - ✅ Examples provided for each level in YAML
- [x] 1.4 Identify "edge-producing" data capabilities
  - ✅ TOP 10 ranked by Impact × (1/Effort) in YAML:
    - Rank 1: Fix portfolio risk (GAP-020) - 10/10 impact, LOW effort
    - Rank 2: Wire options flow (GAP-031) - 9/10 impact, LOW effort
    - Rank 3: Multi-horizon momentum (GAP-012) - 9/10 impact, LOW effort
    - Rank 4: Sector-relative strength (GAP-013) - 8/10 impact, LOW effort
    - Rank 5: Fix position sizing (GAP-043) - 10/10 impact, LOW effort
    - Rank 6: Earnings surprises (GAP-003) - 8/10 impact, LOW effort
    - Rank 7: ATR stops (GAP-042) - 9/10 impact, LOW effort
    - Rank 8: Liquidity checks (GAP-044) - 9/10 impact, LOW effort
    - Rank 9: Drawdown tracking (GAP-023) - 8/10 impact, LOW effort
    - Rank 10: Kelly sizing (GAP-045) - 10/10 impact, MED effort
  - ✅ 4-week MVP roadmap documented in YAML

---

### 2.0 Backend - Gap Detection Engine ✅ COMPLETE

- [x] 2.1 Create gap analysis service
  - File: `backend/app/services/gap_detector.py`
  - Core logic: Compare requirements (from config) vs available capabilities (from scanner)
  - Per-analysis type: Check if required data exists, is fresh, has coverage
  - Per-ticker: Check data availability for specific ticker (e.g., "Can I analyze NVDA fundamentally?")
  - System-wide: Aggregate gaps across all analysis types
- [x] 2.2 Implement coverage calculation
  - Calculate % coverage per analysis type (0-100%)
  - Formula: (available_required_capabilities / total_required_capabilities) * 100
  - Weight by criticality: Required capabilities worth more than optional
  - Consider freshness: Stale data counts as partial coverage only
- [x] 2.3 Add watchlist-specific gap analysis
  - For current watchlist tickers, check coverage per ticker
  - Identify which tickers have good coverage vs poor coverage
  - Highlight analysis types that are blocked for watchlist
  - Example: "Can't do fundamental analysis for 8/12 watchlist tickers (missing earnings data)"
- [x] 2.4 Generate gap recommendations
  - For each gap, suggest specific action to fill it
  - Recommend data sources to fetch from (Alpha Vantage, FMP, Polygon, etc.)
  - Estimate effort to implement (LOW/MEDIUM/HIGH)
  - Prioritize by impact on trading edge (Impact × 1/Effort formula)
  - **CRITICAL NOTE**: Backtesting framework (GAP-019) is prerequisite for validating gap fills
  - Reference gap_definition.md for complete gap specifications (Current State → Desired State → Data Sources)
- [x] 2.5 Create database schema for gap tracking
  - Table: `trading_gaps` (gap_id, analysis_type, capability_name, severity, recommendation, created_at)
  - Table: `gap_resolutions` (gap_id, resolution_date, task_file, status)
  - Migration: Add tables to track identified gaps and their resolution
- [x] 2.6 Add API endpoints
  - `GET /api/gaps/summary` - System-wide gap summary with coverage %
  - `GET /api/gaps/by-analysis` - Gaps grouped by analysis type
  - `GET /api/gaps/by-ticker/:ticker` - Per-ticker gap analysis
  - `GET /api/gaps/watchlist` - Gaps affecting current watchlist
  - `POST /api/gaps/generate-task-list` - Generate task list to fill specific gaps

---

### 3.0 Frontend - Gap Detection UI (Extend Capabilities) - ✅ COMPLETE (6/6 complete)

- [x] 3.1 Add "Gaps" tab to capabilities page ✅
  - Updated page.tsx: Dashboard | Database | Tasks | Endpoints | Insights | **Gaps**
  - Tab shows trading intelligence gaps with gap count badge
  - Integrated with fetchGapSummary API
- [x] 3.2 Create GapsOverview component ✅
  - Shows coverage % per analysis type with progress bars
  - Displays TOP 10 priority gaps with detailed cards
  - Color coding: >80% green, 50-80% yellow, <50% red
  - Maturity level badges (Missing/Minimal/Adequate/Complete)
  - Summary cards (Total Gaps, P0 Critical, P1 High, Avg Coverage)
- [x] 3.3 Create GapsList component ✅
  - Table showing all identified gaps (GapsList.tsx, 332 lines)
  - Columns: Rank | Analysis Type | Missing Capability | Criticality | Severity | Effort | Gap ID
  - Checkbox selection for task list generation
  - Integrated into GapsOverview with "View All Gaps" toggle
- [x] 3.4 Add gap drill-down view ✅
  - Expandable rows showing:
    - Overview: Current State → Desired State
    - Impact: Why it matters + strategies blocked
    - Data Sources: Internal and external sources needed
    - Recommendations: Actionable next steps with effort/priority
- [x] 3.5 Add "Generate Task List" workflow ✅
  - User selects gaps via checkboxes
  - "Generate Task List" button calls `/api/gaps/generate-task-list`
  - Toast notifications for success/failure
  - Shows task file path and "/do_it" instruction
  - Auto-clears selection after generation
- [x] 3.6 Add watchlist coverage view ✅
  - WatchlistCoverage component (275 lines)
  - Matrix view: Tickers (rows) × Analysis Types (columns) → Coverage %
  - Color-coded heat map (green/yellow/red/gray)
  - Expandable ticker rows showing missing capabilities
  - Summary stats (total tickers, analysis types, avg coverage)
  - Lazy loading via React Query

---

### 4.0 AI-Powered Gap Analysis & Recommendations **[DEFERRED TO PHASE 3]**

**⚠️ SKIP THIS TASK DURING PHASE 2 - DEFERRED UNTIL AFTER TASK 0060 COMPLETES**

**Dependency**: This task requires `backend/app/services/ai_analyzer.py` to be working. Currently it uses `Anthropic()` client but no API key exists (broken). Task 0060 Task 3.2a refactors ai_analyzer to use headless Claude CLI, which unblocks this task.

**Execution order**:
1. **Phase 2**: SKIP all Task 4.0 sub-tasks (4.1-4.4) - move to Tasks 5-9 instead
2. **Phase 3**: After Task 0060 completes, return here and complete Task 4.0
3. Verify ai_analyzer.py is working via CLI before starting Task 4.0

**During Phase 2**: Proceed directly from Task 3.6 → Task 5.1 (skip this entire section)

---

- [DEFERRED] 4.1 Add gap analysis to capabilities AI insights
  - Extend existing AI analysis (from Task 0059) to include gap detection
  - Prompt: "Analyze available capabilities vs trading analysis requirements. Identify critical gaps."
  - AI identifies: Missing data, stale data, low coverage, edge-limiting gaps
  - **Requires**: ai_analyzer.py working via CLI (Task 0060 Task 3.2a)
- [DEFERRED] 4.2 Generate actionable recommendations
  - AI suggests: "Missing earnings data blocks fundamental analysis for 60% of watchlist"
  - AI recommends: "Fetch from FMP API (earnings endpoint), estimated 4 hours to implement"
  - AI prioritizes: "High impact - fundamental analysis is critical for value investing strategies"
- [DEFERRED] 4.3 Create gap insights in database
  - Store AI-generated gap insights in `capability_insights` table (reuse existing)
  - Tag with category: "gap_detection"
  - Include confidence score and recommended actions
- [DEFERRED] 4.4 Add "Ask AI" feature for gaps
  - User can ask: "What's blocking better NVDA analysis?"
  - AI responds: "Missing options flow data (can't gauge sentiment), stale fundamentals (earnings 45d old)"
  - AI suggests: "Fetch latest earnings from FMP, add CBOE options flow scraper"

---

### 5.0 Integration with Trading Workflows

- [ ] 5.1 Add gap warnings to watchlist scoring
  - When generating watchlist scores, check if data is complete
  - Show warning: "Score confidence: 60% (missing fundamental data)"
  - Link to gaps tab: "View missing data →"
- [ ] 5.2 Add gap warnings to narrative generation
  - When generating trading narrative, flag missing data
  - Example: "Note: This analysis lacks insider trading data, which could reveal management confidence"
  - Suggest: "Enable insider tracking for deeper insights →"
- [ ] 5.3 Create "Analysis Readiness" indicator
  - For each ticker, show readiness score (0-100%)
  - Based on: Data availability × Data freshness × Coverage completeness
  - Display in watchlist UI: "NVDA: 85% ready (missing options flow)"
- [ ] 5.4 Add gap-based data refresh prioritization
  - Identify which data fetches would fill most critical gaps
  - Prioritize scheduled tasks based on gap severity
  - Example: If fundamental data is biggest gap, prioritize earnings fetcher over others

---

### 6.0 Scheduled Gap Analysis & Monitoring

- [ ] 6.1 Create scheduled gap analysis task
  - Celery task: `analyze_trading_gaps()`
  - Runs daily after capabilities scan (03:30 UTC)
  - Analyzes: New gaps, resolved gaps, coverage trends
  - Outputs: JSON report + logs
- [ ] 6.2 Add gap trending
  - Track coverage % over time (time series)
  - Show: "Fundamental coverage improved from 40% → 65% this month"
  - Identify: Gaps getting worse (data going stale, sources breaking)
- [ ] 6.3 Create gap alerts
  - Alert when critical gap appears (e.g., price data source fails)
  - Alert when coverage drops below threshold (e.g., fundamental coverage <50%)
  - Log to `status_logs` table for visibility
- [ ] 6.4 Add to health monitoring
  - Include gap metrics in system health dashboard
  - Show: "Trading Intelligence Health: 70% (3 critical gaps)"
  - Link to gaps tab for details

---

### 7.0 Documentation & Examples

- [ ] 7.1 Create gap detection user guide
  - File: `docs/reference/trading-gap-detection.md`
  - Explain: What gaps are, why they matter, how to use gap detection
  - Show: Screenshots of gaps UI, coverage matrix, task generation
  - Document: Analysis requirements framework, maturity levels
- [ ] 7.2 Add example gap scenarios
  - Scenario 1: "Missing fundamental data" → How to identify, fill, verify
  - Scenario 2: "Stale news data" → How gap detector flags it, recommended fix
  - Scenario 3: "No options flow" → Impact on sentiment analysis, data sources to add
- [ ] 7.3 Document AI agent workflow
  - How Claude uses gap detection to improve trading insights
  - Example: "Before answering 'Buy NVDA?', check gaps → flag missing data → suggest fixes"
  - Integration with narrative generation and scoring
- [ ] 7.4 Create gap resolution playbook
  - Step-by-step: How to go from gap identified → task list → implementation → verification
  - Template task lists for common gaps (earnings data, insider trading, options flow)
  - Best practices: Prioritization, data source selection, testing

---

### 8.0 Testing & Verification

- [ ] 8.1 Test gap detection logic
  - Unit tests: Coverage calculation, gap identification, recommendation generation
  - Test with mock data: Simulate missing capabilities, verify gaps detected correctly
  - Edge cases: Empty watchlist, all data missing, partial coverage
- [ ] 8.2 Test API endpoints
  - Integration tests: All 4 gap endpoints return correct data
  - Test filters: By analysis type, by ticker, by severity
  - Test task generation: Verify task file created correctly
- [ ] 8.3 Test UI components
  - Component tests: GapsOverview, GapsList render correctly
  - Test interactions: Expand gap, generate task list, navigate to ticker
  - Test watchlist coverage matrix
- [ ] 8.4 End-to-end workflow testing **[PHASE 2 - Manual recommendations only]**
  - Scenario: System has gaps → Manual recommendations → User generates task → Task appears in WORK_TRACKER
  - Verify: Gap recommendations are accurate and actionable
  - Test: Filling a gap actually improves coverage % (close the loop)
  - **Note**: AI-powered workflow ("AI flags them") tested in Phase 3 (Task 8.5)
- [DEFERRED] 8.5 Test AI-powered gap analysis **[PHASE 3 ONLY]**
  - **Note**: Skip during Phase 2, complete in Phase 3 after Task 4.0 done
  - Verify: AI insights identify real gaps (not false positives)
  - Test: Recommendations are practical and prioritized correctly
  - Check: Confidence scores make sense

---

### 9.0 Baseline & Production Deployment

- [ ] 9.1 Run initial gap analysis on current system
  - Execute gap detector against current capabilities
  - Document: What gaps exist today? Coverage % per analysis type?
  - Create: Baseline report (before any improvements)
- [ ] 9.2 Prioritize top 5 gaps to fill first
  - Based on: Impact on trading edge × Effort to implement
  - Generate: Task lists for top 5 gaps
  - Add to WORK_TRACKER as next priorities
- [ ] 9.3 Add to scheduled tasks
  - Enable daily gap analysis task in Celery beat
  - Verify: Task runs successfully, outputs clean reports
  - Monitor: Check logs for errors or anomalies
- [ ] 9.4 Update system documentation
  - Add gap detection to ARCHITECTURE.md (new capability)
  - Update API_REFERENCE.md with gap endpoints
  - Update OPERATIONS.md with gap monitoring procedures

---

## Verification (Phase 2)

**Complete during Phase 2** (skip AI-related items):

- [ ] Backend: Gap detector accurately identifies missing capabilities
- [ ] Backend: Coverage % calculation matches manual verification
- [ ] Backend: Recommendations are actionable and prioritized correctly
- [ ] Backend: Task generation creates valid, executable task files
- [ ] Frontend: Gaps tab shows all gaps grouped by analysis type
- [ ] Frontend: Coverage % displayed correctly with color coding
- [ ] Frontend: Watchlist coverage matrix shows per-ticker gaps
- [ ] Frontend: Generate task list workflow works end-to-end
- [DEFERRED] AI: Gap analysis insights are accurate and helpful **[PHASE 3]**
- [DEFERRED] AI: Recommendations prioritized by trading edge impact **[PHASE 3]**
- [ ] Integration: Gap warnings appear in watchlist/narrative UIs
- [ ] Integration: Analysis readiness scores accurate
- [ ] Scheduled: Daily gap analysis runs and outputs reports
- [ ] Tests: 80%+ coverage, all passing (pytest -v)
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes (ruff + mypy)
- [ ] Docs: User guide complete with examples and screenshots
- [ ] Baseline: Initial gap report generated and documented

---

## Phase 3: After Task 0060 Completes

**Execute AFTER tasks-0060-cli-agent-integration.md is 100% complete**

### Prerequisites
1. Verify Task 0060 Task 3.2a is complete (ai_analyzer.py refactored to use CLI)
2. Test ai_analyzer manually: Should use `claude -p --output-format stream-json`
3. Verify no Anthropic API calls (zero per-token costs)

### Tasks to Complete

1. **Task 4.0: AI-Powered Gap Analysis & Recommendations**
   - [ ] 4.1 Add gap analysis to capabilities AI insights
   - [ ] 4.2 Generate actionable recommendations
   - [ ] 4.3 Create gap insights in database
   - [ ] 4.4 Add "Ask AI" feature for gaps

2. **Task 8.5: Test AI-Powered Gap Analysis**
   - [ ] Verify AI insights identify real gaps
   - [ ] Test recommendations are practical and prioritized
   - [ ] Check confidence scores make sense

3. **Verification (Phase 3 Only)**
   - [ ] AI: Gap analysis insights are accurate and helpful
   - [ ] AI: Recommendations prioritized by trading edge impact

### Completion
- [ ] All Task 4.0 sub-tasks complete
- [ ] Task 8.5 complete
- [ ] AI verification items checked
- [ ] Update WORK_TRACKER.md: Mark Task 0062 as 100% complete
- [ ] Final commit: "feat: complete AI-powered gap analysis (Task 0062 Phase 3)"
