# Task List: Capability Improvements (from /capability_it)

**Source**: Automated analysis via /capability_it
**Complexity**: Medium (targeted improvements)
**Effort**: MEDIUM
**Environment**: Local Dev
**Created**: 2025-12-03
**Generated From**:
  - Capabilities scan: 2025-12-03
  - Insights pending: 0 critical, 2 high, 16 medium/low
  - Gaps: 0 P0, 21 P1 (10 LOW effort), 2 P2

---

## Summary

**Goal**: Address 2 high-priority insights and implement 5 LOW-effort P1 gaps
**Approach**: Fix analyst_revisions task first, then add financial health scores
**Quick Wins**: Piotroski F-Score, Altman Z-Score, News Sentiment Pillar

**Current Health:**
- P0 gaps: 0 (all resolved ✅)
- Pending critical insights: 0 ✅
- Avg gap coverage: 59%

---

## Tasks

### 0.0 Pre-Fix Verification

- [ ] 0.1 Verify services running: `bash ~/portfolio-ai/scripts/status.sh`
- [ ] 0.2 Note current baseline: 0 P0 gaps, 0 critical insights, 59% coverage

### 1.0 Fix High-Priority Insights: Analyst Revisions

**Insight #192 & #182**: analyst_revisions table empty, task not running

- [ ] 1.1 Check if refresh-analyst-revisions-daily task exists in celery_app.py
- [ ] 1.2 Verify task is enabled in beat_schedule
- [ ] 1.3 Check task implementation in services/
- [ ] 1.4 Run task manually to test: `curl -X POST http://localhost:8000/api/...`
- [ ] 1.5 Verify analyst_revisions table populated after task run
- [ ] 1.6 Mark insights #192 and #182 as fixed if resolved

### 2.0 Implement LOW-Effort P1 Gaps: Financial Health Scores

**GAP-008: Piotroski F-Score** (fundamental_analysis, LOW effort)

- [ ] 2.1 Add f_score column to fundamentals_cache or create new table
- [ ] 2.2 Implement F-Score calculation (9-point scoring system)
- [ ] 2.3 Create/update task to calculate F-Score from fundamentals data
- [ ] 2.4 Mark GAP-008 as resolved

**GAP-009: Altman Z-Score** (fundamental_analysis, LOW effort)

- [ ] 2.5 Add z_score column to fundamentals_cache or create new table
- [ ] 2.6 Implement Z-Score calculation (bankruptcy prediction)
- [ ] 2.7 Create/update task to calculate Z-Score from fundamentals data
- [ ] 2.8 Mark GAP-009 as resolved

### 3.0 Implement LOW-Effort P1 Gaps: Risk Metrics

**GAP-027: VaR/CVaR** (risk_analysis, LOW effort)

- [ ] 3.1 Create portfolio_risk_metrics table if not exists
- [ ] 3.2 Implement VaR calculation (historical method)
- [ ] 3.3 Implement CVaR (Expected Shortfall) calculation
- [ ] 3.4 Add daily task to compute risk metrics
- [ ] 3.5 Mark GAP-027 as resolved

**GAP-022: Long-Window Beta** (risk_analysis, LOW effort)

- [ ] 3.6 Extend beta calculation to 1-year and 2-year windows
- [ ] 3.7 Update reference_cache or add new columns
- [ ] 3.8 Mark GAP-022 as resolved

### 4.0 Implement LOW-Effort P1 Gaps: Sentiment

**GAP-015: News Sentiment Pillar** (sentiment_analysis, LOW effort)

- [ ] 4.1 Verify news_cache is being refreshed properly
- [ ] 4.2 Create news_sentiment_aggregation task/service
- [ ] 4.3 Add ticker-level daily sentiment score
- [ ] 4.4 Mark GAP-015 as resolved

---

## Verification

### V.1 Re-scan Capabilities

- [ ] V.1.1 Trigger fresh scan: `curl -sL -X POST http://localhost:8000/api/capabilities/scan`
- [ ] V.1.2 Wait 15 seconds for scan completion
- [ ] V.1.3 Verify health: `curl -sL http://localhost:8000/api/capabilities/health/summary | jq .`

### V.2 Mark Resolved Insights

- [ ] V.2.1 Mark insight #192 as fixed (if resolved)
- [ ] V.2.2 Mark insight #182 as fixed (if resolved)

### V.3 Verify Gap Coverage Improved

- [ ] V.3.1 Check gap summary: `curl -sL http://localhost:8000/api/gaps/summary | jq '{p1: .p1_gaps, avg_coverage: .avg_coverage_pct}'`
- [ ] V.3.2 Target: Coverage should increase from 59% to 65%+

### V.4 Final Quality Check

- [ ] V.4.1 Run lint: `~/portfolio-ai/scripts/lint.sh`
- [ ] V.4.2 Services healthy: `bash ~/portfolio-ai/scripts/status.sh`
- [ ] V.4.3 Take screenshot of /capabilities page

---

## Notes

**Skipped (require external APIs or high effort):**
- GAP-001: Intraday data (needs Polygon subscription)
- GAP-006: Insider trading (MEDIUM effort, needs SEC EDGAR integration)
- GAP-007: Institutional ownership (MEDIUM effort)
- GAP-030: Tick data (needs real-time feed)

**Medium-priority insights to address later:**
- #38: put/call ratio task stale (needs CBOE data investigation)
- #176: symbols table 55% complete (needs data enrichment)
- Strategy metrics tables empty (backlog item)
