# Task List: Capability Improvements (from /capability_it)

**Source**: Automated analysis via /capability_it
**Complexity**: Complex (multi-area improvements)
**Effort**: MEDIUM-HIGH
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-04 03:45
**Generated From**:
  - Capabilities scan: 2025-12-04 03:45
  - Insights: 16 pending (12 critical, 20 high, 15 medium)
  - Gaps: 0 P0, 17 P1, 2 P2 (avg coverage 59%)

---

## Summary

**Goal**: Implement 5 LOW-effort P1 gaps to improve coverage from 59% to ~65%
**Approach**: Focus on internal calculations (no external APIs needed)
**Quick Wins**: 5 items (LOW effort, HIGH impact, no API keys required)

---

## Tasks

### 0.0 Pre-Implementation Verification

- [ ] 0.1 Verify services running: `bash ~/portfolio-ai/scripts/status.sh`
- [ ] 0.2 Note current gap coverage baseline (59%)

### 1.0 Implement LOW-Effort P1 Gaps (Internal Calculations)

**These gaps only require internal calculations from existing data:**

- [ ] 1.1 **GAP-008: Piotroski F-Score** (fundamental_analysis)
  - Current: No composite quality score
  - Target: 9-point Piotroski F-Score (profitability + leverage + efficiency)
  - Source: Internal calculation from fundamentals_cache
  - Effort: LOW
  - Files: `backend/app/services/fundamentals.py`

- [ ] 1.2 **GAP-009: Altman Z-Score** (fundamental_analysis)
  - Current: No bankruptcy prediction
  - Target: Altman Z-Score (Z < 1.8 = distress)
  - Source: Internal calculation from balance sheet data
  - Effort: LOW
  - Files: `backend/app/services/fundamentals.py`

- [ ] 1.3 **GAP-027: VaR/CVaR** (risk_analysis)
  - Current: No Value at Risk or Conditional VaR
  - Target: 1-day VaR (95%), CVaR (expected loss beyond VaR)
  - Source: Internal calculation from portfolio_snapshots (historical returns)
  - Effort: LOW
  - Files: `backend/app/services/risk/` or new risk module

- [ ] 1.4 **GAP-022: Beta Estimation (Long Window)** (risk_analysis)
  - Current: Only 90-day betas (noisy)
  - Target: 3-5 year betas with Bayesian shrinkage
  - Source: Internal calculation from day_bars
  - Effort: LOW
  - Files: `backend/app/services/technicals.py` or risk module

- [ ] 1.5 **GAP-025: Stress Testing** (risk_analysis)
  - Current: No scenario analysis
  - Target: 2008 crisis, 2020 COVID, VIX=80 scenarios
  - Source: Internal historical correlation + shocks
  - Effort: LOW
  - Files: New module `backend/app/services/stress_testing.py`

### 2.0 Additional LOW-Effort Gaps (If Time Permits)

- [ ] 2.1 **GAP-026: Marginal VaR** (risk_analysis)
  - Current: Don't know which position adds most risk
  - Target: Marginal VaR per position (risk contribution)
  - Source: Calculated from covariance matrix
  - Effort: LOW

- [ ] 2.2 **GAP-028: Exposure Budgets** (risk_analysis)
  - Current: No limits on sector/factor/single-name exposure
  - Target: Max 10% per position, 30% per sector
  - Source: Portfolio holdings + sector mapping
  - Effort: LOW

- [ ] 2.3 **GAP-015: News Sentiment Pillar** (sentiment_analysis)
  - Current: News exists but only a modifier, not a pillar
  - Target: News sentiment as dedicated scoring pillar (15-20% weight)
  - Source: news_cache (already populated)
  - Effort: LOW

- [ ] 2.4 **GAP-050: Feature Engineering Pipeline** (ml_infrastructure)
  - Current: No ML feature pipeline
  - Target: Transform raw data into ML features
  - Source: All tables
  - Effort: LOW

- [ ] 2.5 **GAP-053: Wash Sale Detection** (compliance)
  - Current: No wash sale tracking
  - Target: Detect: Sell at loss + rebuy within 30 days
  - Source: Order history, trade history
  - Effort: LOW

---

## Verification

### V.1 Re-scan and Verify Coverage

- [ ] V.1.1 Trigger fresh scan: `curl -sL -X POST http://localhost:8000/api/capabilities/scan`
- [ ] V.1.2 Wait 10 seconds for scan completion
- [ ] V.1.3 Check gap coverage improved:
  ```bash
  curl -sL http://localhost:8000/api/gaps/summary | jq '{avg_coverage: .avg_coverage_pct, p1: .p1_gaps}'
  ```
- [ ] V.1.4 Verify target: avg_coverage > 65%

### V.2 Mark Resolved Gaps

For each gap we implemented, verify and mark resolved:
```bash
curl -sL -X POST "http://localhost:8000/api/gaps/GAP-XXX/resolve" \
  -H "Content-Type: application/json" \
  -d '{"resolution_notes": "Implemented via /capability_it"}'
```

### V.3 Final Quality Check

- [ ] V.3.1 Run lint: `~/portfolio-ai/scripts/lint.sh`
- [ ] V.3.2 Services healthy: `bash ~/portfolio-ai/scripts/status.sh`

---

## Notes

**Skipped (require external APIs):**
- GAP-001, GAP-030, GAP-038: Intraday/tick data (needs Polygon/Alpaca subscription)
- GAP-006, GAP-007, GAP-011: Insider/institutional data (needs Finnhub/SEC setup)
- GAP-002, GAP-004: Valuation/cash flow (needs FMP/Finnhub)
- GAP-033: Ticker put/call ratio (needs Polygon/Tradier)
- GAP-034, GAP-035, GAP-036: Macro data (needs FRED setup)
- GAP-048: Slippage tracking (needs broker integration)

**These can be addressed in future capability_it runs after API setup.**
