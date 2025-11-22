# Task List: Investment Intelligence Confidence Scoring Completion

**Source**: User request via /task_it - VISION.md Gap Analysis Priority #3
**Complexity**: Medium
**Effort**: MEDIUM (5-7 hours)
**Environment**: Local Dev
**Created**: 2025-11-22 14:25

---

## Summary

**Goal**: Achieve VISION.md compliance for Investment Intelligence confidence scoring by integrating fundamental data thresholds and analyst sentiment into graded weighting system, where EXCELLENT companies contribute more to confidence than GOOD companies

**Approach**: Refactor signal_classifier.py to apply multi-tier fundamental scoring (profit margin, revenue growth, debt health, analyst consensus) as 0-5 point components instead of binary checks, and add analyst recommendation weighting (1-5 scale → confidence adjustment)

**Scope Discovery**: Not needed (2-3 known files, clear requirements)

---

## Tasks

### 1.0 Add Fundamental Component Scoring to Signal Classification

- [ ] 1.1 Open `backend/app/watchlist/signal_classifier.py`
- [ ] 1.2 Create helper function `_calculate_fundamental_component_score()`:
  ```python
  def _calculate_fundamental_component_score(
      profit_margin: float | None,
      revenue_growth: float | None,
      debt_to_equity: float | None,
  ) -> tuple[int, list[str]]:
      """Calculate 0-5 point fundamental component score.

      Returns:
          (score, reasons) where score ranges 0-5 based on:
          - Profit margin: +2 if >20%, +1 if 5-20%, 0 if <5%
          - Revenue growth: +2 if >20%, +1 if 5-20%, 0 if <5% or negative
          - Debt health: +1 if <0.5, +0 if 0.5-1.5, -1 if >1.5
      """
  ```
- [ ] 1.3 Implement profit margin scoring tier logic:
  - Exceptional (>20%): +2 points, reason: "Very profitable - {margin}%"
  - Good (5-20%): +1 point, reason: "Profitable - {margin}%"
  - Weak (<5%): 0 points, no addition
  - Negative: -1 point, reason: "Unprofitable - {margin}%"
- [ ] 1.4 Implement revenue growth scoring tier logic:
  - Strong growth (>20%): +2 points, reason: "Strong growth - {growth}%"
  - Moderate growth (5-20%): +1 point, reason: "Growing - {growth}%"
  - Weak/declining (<5%): 0 points, no addition
  - Shrinking (negative): -1 point, reason: "Revenue declining"
- [ ] 1.5 Implement debt health scoring tier logic:
  - Low debt (<0.5): +1 point, reason: "Low debt - strong balance sheet"
  - Moderate debt (0.5-1.5): 0 points
  - High debt (>1.5): -1 point, reason: "High debt - balance sheet concern"
- [ ] 1.6 Return total score (range -3 to +5) with detailed reasons list

### 2.0 Add Analyst Sentiment Scoring to Signal Classification

- [ ] 2.1 Create helper function `_calculate_analyst_component_score()`:
  ```python
  def _calculate_analyst_component_score(
      recommendation_mean: float | None,
      analyst_buy_pct: float | None,
  ) -> tuple[int, list[str]]:
      """Calculate 0-5 point analyst component score.

      Analyst recommendation scale: 1.0=strong buy, 5.0=sell

      Returns:
          (score, reasons) where score ranges 0-5 based on:
          - Recommendation mean: +3 if <2.0, +2 if 2.0-2.5, +1 if 2.5-3.0, 0 if >3.0
          - Analyst buy %: +2 if >70%, +1 if 50-70%, 0 if <50%
      """
  ```
- [ ] 2.2 Implement recommendation mean scoring:
  - Strong buy consensus (<2.0): +3 points, reason: "Analyst strong buy - {mean:.1f}/5.0"
  - Buy consensus (2.0-2.5): +2 points, reason: "Analyst buy - {mean:.1f}/5.0"
  - Hold consensus (2.5-3.0): +1 point, reason: "Analyst hold - {mean:.1f}/5.0"
  - Sell consensus (>3.0): 0 points, no addition
- [ ] 2.3 Implement analyst buy percentage scoring:
  - Strong buy % (>70%): +2 points, reason: "{buy_pct}% analysts recommend buy"
  - Moderate buy % (50-70%): +1 point
  - Low buy % (<50%): 0 points
- [ ] 2.4 Return total score (range 0-5) with detailed reasons

### 3.0 Integrate Component Scores into Main Signal Classification

- [ ] 3.1 Locate `classify_signal()` function in signal_classifier.py (currently line ~236)
- [ ] 3.2 Add fundamental component calculation after technical checks:
  ```python
  # After line ~213 (after technical confirmations)
  fundamental_score, fundamental_reasons = _calculate_fundamental_component_score(
      profit_margin=data.get("profit_margin"),
      revenue_growth=data.get("revenue_growth"),
      debt_to_equity=data.get("debt_to_equity"),
  )
  confirmations += fundamental_score
  reasons.extend(fundamental_reasons)
  ```
- [ ] 3.3 Add analyst component calculation:
  ```python
  analyst_score, analyst_reasons = _calculate_analyst_component_score(
      recommendation_mean=data.get("recommendation_mean"),
      analyst_buy_pct=data.get("analyst_buy_pct"),
  )
  confirmations += analyst_score
  reasons.extend(analyst_reasons)
  ```
- [ ] 3.4 Update `_calculate_signal_strength()` to handle expanded range:
  - Current range: 0-8 confirmations (8 BUY checks)
  - New range: -3 to 18 confirmations (8 technical + 5 fundamental + 5 analyst)
  - Adjust strength mapping to 0-10 scale: `strength = max(0, min(10, int((confirmations + 3) / 2.1)))`
- [ ] 3.5 Update docstring to document new scoring components

### 4.0 Scale News Sentiment to Continuous Contribution

- [ ] 4.1 Locate news sentiment check (currently line ~200-203)
- [ ] 4.2 Replace binary check with scaled contribution:
  ```python
  # Old: if data["news_sentiment"] >= 0.2: confirmations += 1
  # New:
  if data["news_sentiment"] is not None:
      sentiment_score = (data["news_sentiment"] + 1.0) / 2.0 * 5.0  # Scale -1..+1 to 0..5
      confirmations += int(sentiment_score)
      if data["news_sentiment"] >= 0.2:
          reasons.append(f"News sentiment {data['news_sentiment']:.2f} (positive)")
      elif data["news_sentiment"] <= -0.3:
          reasons.append(f"News sentiment {data['news_sentiment']:.2f} (negative)")
  ```
- [ ] 4.3 Update strength calculation to account for 0-5 news contribution

### 5.0 Update Signal Data Inputs to Include New Fields

- [ ] 5.1 Open `backend/app/watchlist/refresh_narrative.py`
- [ ] 5.2 Locate `build_signal_inputs()` function (currently line ~59)
- [ ] 5.3 Add fundamental data fields to signal inputs dictionary:
  ```python
  "profit_margin": fundamental_data.profit_margin if fundamental_data else None,
  "revenue_growth": fundamental_data.revenue_growth if fundamental_data else None,
  "debt_to_equity": fundamental_data.debt_to_equity if fundamental_data else None,
  "recommendation_mean": fundamental_data.recommendation_mean if fundamental_data else None,
  "analyst_buy_pct": calculate_analyst_buy_pct(fundamental_data) if fundamental_data else None,
  ```
- [ ] 5.4 Create `calculate_analyst_buy_pct()` helper if needed:
  - Calculate from num_analyst_opinions if available
  - Or extract from existing fundamental data structure
- [ ] 5.5 Verify fundamental_data is available in refresh context

### 6.0 Add Unit Tests for New Scoring Logic

- [ ] 6.1 Create or update `backend/tests/watchlist/test_signal_classifier.py`
- [ ] 6.2 Add test for fundamental component scoring:
  ```python
  def test_calculate_fundamental_component_score_excellent():
      score, reasons = _calculate_fundamental_component_score(
          profit_margin=0.35,  # 35% = +2
          revenue_growth=0.25,  # 25% = +2
          debt_to_equity=0.3,  # Low debt = +1
      )
      assert score == 5  # Maximum score
      assert len(reasons) == 3
  ```
- [ ] 6.3 Add test for analyst component scoring:
  ```python
  def test_calculate_analyst_component_score_strong_buy():
      score, reasons = _calculate_analyst_component_score(
          recommendation_mean=1.8,  # Strong buy = +3
          analyst_buy_pct=75.0,  # >70% = +2
      )
      assert score == 5  # Maximum score
  ```
- [ ] 6.4 Add test for integrated signal classification:
  - Test BUY signal with EXCELLENT fundamentals (higher strength)
  - Test BUY signal with GOOD fundamentals (medium strength)
  - Test HOLD signal with mixed fundamentals
- [ ] 6.5 Add test for continuous news sentiment:
  - Test strong positive sentiment (+0.8 → ~4.5 points)
  - Test weak positive sentiment (+0.2 → ~3.0 points)
  - Test negative sentiment (-0.5 → ~1.25 points)
- [ ] 6.6 Run tests and verify all passing:
  ```bash
  cd ~/portfolio-ai/backend && source .venv/bin/activate && pytest tests/watchlist/test_signal_classifier.py -v
  ```

### 7.0 Integration Testing and Validation

- [ ] 7.1 Test with real watchlist refresh:
  ```bash
  cd ~/portfolio-ai/backend && source .venv/bin/activate && python -c "from app.watchlist.refresh_processor import refresh_watchlist_item; refresh_watchlist_item('AAPL')"
  ```
- [ ] 7.2 Verify signal strength differences for EXCELLENT vs GOOD companies:
  - Query database for companies with different health classifications
  - Confirm EXCELLENT companies have higher signal_strength than GOOD for similar technical setups
- [ ] 7.3 Verify analyst sentiment impact:
  - Find ticker with strong analyst buy (recommendation_mean < 2.0)
  - Confirm signal_strength reflects analyst consensus
- [ ] 7.4 Check narrative reasons include fundamental/analyst details:
  - Verify `SignalClassification.reasons` list includes new component reasons
  - Check frontend display shows expanded reasoning
- [ ] 7.5 Restart services to load changes:
  ```bash
  bash ~/portfolio-ai/scripts/restart.sh
  ```

### 8.0 Documentation and VISION Compliance

- [ ] 8.1 Update `docs/reference/vision-gap-analysis-2025-11-22.md`:
  - Mark Gap 1.1 (Analyst Sentiment) as RESOLVED
  - Mark Gap 1.2 (Fundamental Thresholds) as RESOLVED
  - Mark Gap 1.3 (News Sentiment Continuous) as RESOLVED
- [ ] 8.2 Update `docs/core/ARCHITECTURE.md`:
  - Document new confidence scoring formula
  - Explain fundamental component weighting (0-5 points)
  - Explain analyst component weighting (0-5 points)
  - Document strength scaling (0-18 confirmations → 0-10 strength)
- [ ] 8.3 Verify VISION.md compliance:
  - ✅ "Confidence Scoring (0-10 with evidence)" - NOW FULLY COMPLIANT
  - ✅ Fundamental data integrated with graded weighting
  - ✅ Analyst sentiment factored into signal strength
  - ✅ Continuous news sentiment contribution
- [ ] 8.4 Update gap analysis report:
  - Investment Intelligence: 85% → 98% complete
  - Overall VISION alignment: 85% → 91% (with Priorities 1-3 complete)

---

## Verification

- [ ] Functional: All scoring components integrated and working
- [ ] Tests: New unit tests passing, integration tests verify behavior
- [ ] Quality: ~/portfolio-ai/scripts/lint.sh passes (ruff + mypy --strict)
- [ ] Services: Restarted and verified with manual refresh
- [ ] Database: signal_strength values reflect new scoring (higher for EXCELLENT companies)
- [ ] Frontend: Narrative reasons display fundamental/analyst details
- [ ] Docs: ARCHITECTURE.md and gap analysis updated
- [ ] VISION: Confidence scoring requirement fully met (85% → 98% Investment Intelligence compliance)

---

## Technical Notes

**Existing Infrastructure:**
- Signal classifier: `backend/app/watchlist/signal_classifier.py` (287 lines)
- Fundamental data: `backend/app/watchlist/fundamentals.py` (533 lines, 4-pillar scoring)
- Refresh orchestration: `backend/app/watchlist/refresh_narrative.py` (builds signal inputs)

**Current Scoring (Binary Checks):**
- 8 technical BUY confirmations (EMA, RSI, MACD, volume, health, sentiment, not overbought, strong uptrend)
- Company health binary: in ("EXCELLENT", "GOOD") = +1, else 0
- Analyst sentiment: fetched but NOT used
- News sentiment: binary >= 0.2 = +1, else 0

**New Scoring (Graded Components):**
- 8 technical confirmations (unchanged)
- Fundamental component: -3 to +5 points (profit margin, revenue growth, debt)
- Analyst component: 0 to +5 points (recommendation mean, buy %)
- News sentiment: 0 to +5 points (scaled from -1..+1 range)
- **Total range**: -3 to +18 confirmations
- **Strength mapping**: `(confirmations + 3) / 2.1` → 0-10 scale

**Expected Behavior After Fix:**
- EXCELLENT companies (50% margin, 50% growth, low debt): +5 fundamental points → strength 8-10
- GOOD companies (15% margin, 10% growth, moderate debt): +2-3 fundamental points → strength 6-8
- WEAK companies (negative margin, declining revenue, high debt): -2 to 0 points → strength 3-5
- Strong analyst buy (<2.0 mean, >70% buy): +5 analyst points → significant strength boost
- Strong positive news (+0.7 sentiment): +4 news points → moderate strength boost

**Verification Queries:**
```bash
# Check signal strength distribution before/after
cd ~/portfolio-ai/backend && source .venv/bin/activate && python -c "from app.storage import get_storage; storage = get_storage(); print(storage.query('SELECT company_health, AVG(signal_strength) as avg_strength, COUNT(*) as count FROM watchlist_snapshots WHERE signal_type = \"BUY\" GROUP BY company_health'))"

# Check reasons detail level
cd ~/portfolio-ai/backend && source .venv/bin/activate && python -c "from app.watchlist.signal_classifier import classify_signal; print(classify_signal({...}))"
```

**VISION Compliance Impact:**
- Current: 85% Investment Intelligence compliance (missing fundamental weighting)
- After fix: 98% Investment Intelligence compliance (only minor gaps like volume spike detection remain)
- Overall system: 85% → 91% VISION alignment (with all 3 priorities complete)
