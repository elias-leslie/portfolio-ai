# Task List: Trading Intelligence Gap Detection

**Source**: User request via /task_it
**Complexity**: Complex
**Effort**: HIGH (15-20 hours)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-13 23:45

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

- [ ] 0.1 Run Explore subagent in "medium" mode
  - Understand current capabilities system architecture (scanner, API, data models)
  - Find existing trading data sources (what tables/tasks/endpoints exist for market data?)
  - Identify analysis patterns (how do we currently analyze stocks? watchlist scoring? narrative generation?)
  - Map available data: price, volume, news, fundamentals, technical indicators, options, etc.
- [ ] 0.2 Document findings and update task list
  - List all available data capabilities (what we HAVE)
  - Identify existing analysis workflows that would benefit from gap detection
  - Determine integration points with capabilities feature
  - Update effort estimates based on actual architecture
- [ ] 0.3 Checkpoint: Confirm scope before proceeding
  - Available data sources: [TBD]
  - Analysis types we can already support: [TBD]
  - Integration approach: [TBD]
  - Estimated effort: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

---

### 1.0 Define Trading Analysis Requirements Framework

- [ ] 1.1 Create analysis requirements taxonomy
  - Define what data each analysis type needs (comprehensive, market wizard level)
  - Technical Analysis: OHLCV, volume, technical indicators, chart patterns, support/resistance
  - Fundamental Analysis: Earnings, revenue, margins, cash flow, P/E, P/B, PEG, growth rates, guidance
  - Sentiment Analysis: News sentiment, analyst ratings, options flow (put/call), social sentiment, insider trading
  - Risk Analysis: Volatility, beta, correlation, Sharpe ratio, max drawdown, position sizing
  - Macro Analysis: Fed policy, rates, inflation, sector rotation, economic indicators
  - Event Analysis: Earnings dates, ex-dividend dates, splits, M&A, regulatory events
- [ ] 1.2 Create requirements configuration file
  - Format: YAML or JSON defining required/recommended/optional data per analysis type
  - Example: `trading_requirements.yaml` with structure: analysis_type → data_capability → criticality
  - Include freshness requirements (e.g., price data must be <1 day old, fundamentals <90 days)
  - Include coverage requirements (e.g., need earnings for 80% of tickers to do fundamental analysis)
- [ ] 1.3 Define data capability maturity levels
  - Level 0: Missing (no data, can't perform analysis)
  - Level 1: Minimal (basic data, limited insights)
  - Level 2: Adequate (good coverage, reasonable insights)
  - Level 3: Complete (comprehensive data, strong edge potential)
  - Document what each level means per analysis type
- [ ] 1.4 Identify "edge-producing" data capabilities
  - What data separates good from great trading insights?
  - Examples: Real-time options flow, insider trading patterns, earnings call sentiment, unusual volume
  - Mark these as high-priority gaps to fill

---

### 2.0 Backend - Gap Detection Engine

- [ ] 2.1 Create gap analysis service
  - File: `backend/app/services/gap_detector.py`
  - Core logic: Compare requirements (from config) vs available capabilities (from scanner)
  - Per-analysis type: Check if required data exists, is fresh, has coverage
  - Per-ticker: Check data availability for specific ticker (e.g., "Can I analyze NVDA fundamentally?")
  - System-wide: Aggregate gaps across all analysis types
- [ ] 2.2 Implement coverage calculation
  - Calculate % coverage per analysis type (0-100%)
  - Formula: (available_required_capabilities / total_required_capabilities) * 100
  - Weight by criticality: Required capabilities worth more than optional
  - Consider freshness: Stale data counts as partial coverage only
- [ ] 2.3 Add watchlist-specific gap analysis
  - For current watchlist tickers, check coverage per ticker
  - Identify which tickers have good coverage vs poor coverage
  - Highlight analysis types that are blocked for watchlist
  - Example: "Can't do fundamental analysis for 8/12 watchlist tickers (missing earnings data)"
- [ ] 2.4 Generate gap recommendations
  - For each gap, suggest specific action to fill it
  - Recommend data sources to fetch from (Alpha Vantage, FMP, Polygon, etc.)
  - Estimate effort to implement (LOW/MEDIUM/HIGH)
  - Prioritize by impact on trading edge
- [ ] 2.5 Create database schema for gap tracking
  - Table: `trading_gaps` (gap_id, analysis_type, capability_name, severity, recommendation, created_at)
  - Table: `gap_resolutions` (gap_id, resolution_date, task_file, status)
  - Migration: Add tables to track identified gaps and their resolution
- [ ] 2.6 Add API endpoints
  - `GET /api/gaps/summary` - System-wide gap summary with coverage %
  - `GET /api/gaps/by-analysis` - Gaps grouped by analysis type
  - `GET /api/gaps/by-ticker/:ticker` - Per-ticker gap analysis
  - `GET /api/gaps/watchlist` - Gaps affecting current watchlist
  - `POST /api/gaps/generate-task-list` - Generate task list to fill specific gaps

---

### 3.0 Frontend - Gap Detection UI (Extend Capabilities)

- [ ] 3.1 Add "Gaps" tab to capabilities page
  - Update page.tsx: Dashboard | Database | Tasks | Endpoints | Insights | **Gaps**
  - Tab shows trading intelligence gaps, not just missing tables
- [ ] 3.2 Create GapsOverview component
  - Show coverage % per analysis type (Technical: 85%, Fundamental: 45%, Sentiment: 30%, etc.)
  - Visual: Progress bars or radial charts showing coverage
  - Color coding: >80% green, 50-80% yellow, <50% red
  - Click analysis type → drill down to specific gaps
- [ ] 3.3 Create GapsList component
  - Table showing all identified gaps
  - Columns: Analysis Type | Missing Capability | Severity | Impact | Recommendation | Actions
  - Severity: Critical (blocks analysis), High (reduces edge), Medium (nice to have)
  - Impact: How much this gap hurts trading insights (High/Medium/Low)
- [ ] 3.4 Add gap drill-down view
  - Click gap → expandable row showing:
    - Why this matters (what insights are we missing?)
    - What data sources could fill it (FMP, Polygon, Alpha Vantage, etc.)
    - Estimated effort to implement (hours)
    - Example use case (concrete trading scenario this would help)
- [ ] 3.5 Add "Generate Task List" workflow
  - User selects gaps to fill (checkboxes)
  - Click "Generate Task List" → calls `/api/gaps/generate-task-list`
  - Backend creates task file (e.g., `tasks-XXXX-fill-fundamental-gaps.md`)
  - Frontend shows: "Task list created! Run /do_it to start implementation"
- [ ] 3.6 Add watchlist coverage view
  - Show per-ticker coverage for current watchlist
  - Matrix view: Tickers (rows) × Analysis Types (columns) → Coverage %
  - Highlight tickers with poor coverage (can't analyze properly)
  - Show what's missing per ticker (e.g., "NVDA: Missing insider trading data")

---

### 4.0 AI-Powered Gap Analysis & Recommendations

- [ ] 4.1 Add gap analysis to capabilities AI insights
  - Extend existing AI analysis (from Task 0059) to include gap detection
  - Prompt: "Analyze available capabilities vs trading analysis requirements. Identify critical gaps."
  - AI identifies: Missing data, stale data, low coverage, edge-limiting gaps
- [ ] 4.2 Generate actionable recommendations
  - AI suggests: "Missing earnings data blocks fundamental analysis for 60% of watchlist"
  - AI recommends: "Fetch from FMP API (earnings endpoint), estimated 4 hours to implement"
  - AI prioritizes: "High impact - fundamental analysis is critical for value investing strategies"
- [ ] 4.3 Create gap insights in database
  - Store AI-generated gap insights in `capability_insights` table (reuse existing)
  - Tag with category: "gap_detection"
  - Include confidence score and recommended actions
- [ ] 4.4 Add "Ask AI" feature for gaps
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
- [ ] 8.4 End-to-end workflow testing
  - Scenario: System has gaps → AI flags them → User generates task → Task appears in WORK_TRACKER
  - Verify: Gap recommendations are accurate and actionable
  - Test: Filling a gap actually improves coverage % (close the loop)
- [ ] 8.5 Test AI-powered gap analysis
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

## Verification

- [ ] Backend: Gap detector accurately identifies missing capabilities
- [ ] Backend: Coverage % calculation matches manual verification
- [ ] Backend: Recommendations are actionable and prioritized correctly
- [ ] Backend: Task generation creates valid, executable task files
- [ ] Frontend: Gaps tab shows all gaps grouped by analysis type
- [ ] Frontend: Coverage % displayed correctly with color coding
- [ ] Frontend: Watchlist coverage matrix shows per-ticker gaps
- [ ] Frontend: Generate task list workflow works end-to-end
- [ ] AI: Gap analysis insights are accurate and helpful
- [ ] AI: Recommendations prioritized by trading edge impact
- [ ] Integration: Gap warnings appear in watchlist/narrative UIs
- [ ] Integration: Analysis readiness scores accurate
- [ ] Scheduled: Daily gap analysis runs and outputs reports
- [ ] Tests: 80%+ coverage, all passing (pytest -v)
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes (ruff + mypy)
- [ ] Docs: User guide complete with examples and screenshots
- [ ] Baseline: Initial gap report generated and documented
