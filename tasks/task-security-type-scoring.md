# Task: Security-Type-Aware Scoring

**Status**: Not Started
**Created**: 2025-12-10
**Complexity**: Medium-High
**Estimated Effort**: MEDIUM (algorithmic changes, weight redistribution logic)

## Overview

Make the AI scoring system aware of security types (ETF vs stock) and adjust which pillars apply based on what makes sense for that security. ETFs don't have P/E ratios or earnings announcements, so fundamental and certain catalyst pillars should be excluded with weights redistributed dynamically to other applicable pillars.

## Description

The Security-Type-Aware Scoring system will:
- Detect security type from `symbols` table (`security_type` column)
- Apply different pillar configurations based on security type
- Dynamically redistribute weights when pillars are N/A
- Maintain score comparability across security types
- Prepare for future security-type-specific metrics (e.g., ETF expense ratios)

## Acceptance Criteria

### AC-1: Security Type Detection
- [ ] `symbols` table has `security_type` column (ENUM: 'stock', 'etf', 'other')
- [ ] Security type populated for all watchlist symbols
- [ ] Fallback logic: default to 'stock' if unknown
- [ ] UI displays security type badge in watchlist (optional enhancement)

### AC-2: Pillar Applicability Rules
- [ ] **Stocks**: All 5 pillars apply (Technical, Fundamental, Catalyst, Options, Price)
- [ ] **ETFs**: Exclude certain sub-pillars:
  - Fundamental: Exclude P/E ratio, profit margins, revenue growth
  - Fundamental: Keep market cap, volume, volatility (if applicable)
  - Catalyst: Exclude earnings-related catalysts
  - Catalyst: Keep other catalysts (SEC filings, news sentiment)
  - Technical, Options, Price: Keep all
- [ ] Rules configurable via YAML or database (not hardcoded)

### AC-3: Dynamic Weight Redistribution
- [ ] When a pillar is marked N/A, its weight is redistributed proportionally
- [ ] Example for ETF (default stock weights):
  ```
  Stock weights:
    Technical: 25%, Fundamental: 25%, Catalyst: 20%, Options: 15%, Price: 15%

  ETF (Fundamental 50% excluded, Catalyst 40% excluded):
    Excluded weight: 25% * 0.5 + 20% * 0.4 = 12.5% + 8% = 20.5%
    Remaining pillars scale up:
      Technical: 25% → 30.5%
      Fundamental: 12.5% → 15.2%  (50% applicable)
      Catalyst: 12% → 14.6%       (60% applicable)
      Options: 15% → 18.3%
      Price: 15% → 18.3%
    Total: 100%
  ```
- [ ] Redistribution algorithm is transparent and auditable
- [ ] Score remains 0-100 scale regardless of security type

### AC-4: Backend Scoring Changes
- [ ] `calculate_watchlist_scores()` checks security type before scoring
- [ ] Pillar calculations skip N/A sub-components
- [ ] Weight redistribution applied during final score calculation
- [ ] `raw_metrics` includes:
  - `security_type`
  - `applicable_pillars` (list of pillar IDs that were used)
  - `weight_adjustments` (before/after weights)
  - Original score breakdown per pillar
- [ ] API response includes security type and adjusted weights

### AC-5: Scoring Transparency
- [ ] Watchlist API response shows:
  ```json
  {
    "symbol": "SPY",
    "security_type": "etf",
    "current_score": 78,
    "score_breakdown": {
      "technical": {"score": 85, "weight": 0.305, "original_weight": 0.25},
      "fundamental": {"score": 70, "weight": 0.152, "original_weight": 0.25, "partial": true},
      "catalyst": {"score": 65, "weight": 0.146, "original_weight": 0.20, "partial": true},
      "options": {"score": 80, "weight": 0.183, "original_weight": 0.15},
      "price": {"score": 75, "weight": 0.183, "original_weight": 0.15}
    }
  }
  ```
- [ ] Tooltip in UI explains weight adjustments on hover
- [ ] Users understand why ETF scores may differ structurally from stocks

### AC-6: Future ETF-Specific Metrics (Foundation)
- [ ] Architecture supports adding ETF-specific scoring in future:
  - Expense ratio (lower is better)
  - AUM (higher is better for liquidity)
  - Tracking error (lower is better)
  - Holdings diversification
- [ ] Config file documents placeholder for ETF-specific weights
- [ ] Database schema allows storing ETF fundamentals separately

## Implementation Steps

### Step 1: Database - Add Security Type Column
**File**: `backend/app/storage/schema.sql`

1. Add migration to create `security_type` column:
   ```sql
   ALTER TABLE symbols
   ADD COLUMN security_type VARCHAR(20) DEFAULT 'stock' NOT NULL;

   CREATE TYPE security_type_enum AS ENUM ('stock', 'etf', 'other');
   ALTER TABLE symbols
   ALTER COLUMN security_type TYPE security_type_enum USING security_type::security_type_enum;
   ```
2. Populate security type from existing data:
   - Check symbol suffixes (e.g., ETFs often end with specific patterns)
   - Use yfinance to detect ETF vs stock
   - Manually classify major ETFs (SPY, QQQ, IWM, etc.)
3. Add index: `CREATE INDEX idx_symbols_security_type ON symbols(security_type);`

**Files to modify**:
- `backend/app/storage/schema.sql`
- `backend/migrations/XXX_add_security_type.sql` (new)

### Step 2: Backend - Security Type Detection Service
**File**: `backend/app/services/security_type_service.py` (new)

1. Create `SecurityTypeService` class
2. Implement `detect_security_type(symbol: str) -> SecurityType`:
   - Query symbols table first (cache)
   - If unknown, fetch from yfinance (`info['quoteType']`)
   - Map yfinance types to our enum
3. Implement `bulk_detect_security_types(symbols: list[str])` for batch operations
4. Add caching layer (Redis or in-memory)
5. Write unit tests (15+ tests)

**Files to create**:
- `backend/app/services/security_type_service.py`
- `backend/tests/unit/test_security_type_service.py`

### Step 3: Backend - Pillar Applicability Configuration
**File**: `backend/app/config/scoring_rules.yaml` (new)

1. Create YAML config for pillar applicability:
   ```yaml
   security_types:
     stock:
       pillars:
         technical: {enabled: true, weight: 0.25}
         fundamental: {enabled: true, weight: 0.25}
         catalyst: {enabled: true, weight: 0.20}
         options: {enabled: true, weight: 0.15}
         price: {enabled: true, weight: 0.15}

     etf:
       pillars:
         technical: {enabled: true, weight: 0.25}
         fundamental:
           enabled: partial  # Some metrics apply, others don't
           weight: 0.25
           exclude_metrics: [pe_ratio, profit_margin, revenue_growth, earnings_growth]
           keep_metrics: [market_cap, avg_volume, beta]
         catalyst:
           enabled: partial
           weight: 0.20
           exclude_types: [earnings, earnings_call, earnings_surprise]
           keep_types: [sec_filing, insider_transaction, news_sentiment]
         options: {enabled: true, weight: 0.15}
         price: {enabled: true, weight: 0.15}
   ```
2. Create loader: `ScoringRulesConfig` class
3. Add validation logic

**Files to create**:
- `backend/app/config/scoring_rules.yaml`
- `backend/app/config/scoring_rules.py` (loader class)

### Step 4: Backend - Weight Redistribution Service
**File**: `backend/app/services/weight_redistribution.py` (new)

1. Create `WeightRedistributor` class
2. Implement `calculate_adjusted_weights()` method:
   - Input: security type, original weights, pillar applicability
   - Output: adjusted weights that sum to 1.0
3. Algorithm:
   ```python
   def redistribute_weights(original_weights, applicability):
       excluded_weight = sum(w * (1 - a) for w, a in zip(original_weights, applicability))
       applicable_weight = sum(w * a for w, a in zip(original_weights, applicability))

       adjusted_weights = []
       for original_w, applicable_pct in zip(original_weights, applicability):
           if applicable_pct == 0:
               adjusted_weights.append(0)
           else:
               # Scale up by the ratio of excluded weight
               scaling_factor = 1 + (excluded_weight / applicable_weight)
               adjusted_weights.append(original_w * applicable_pct * scaling_factor)

       return adjusted_weights
   ```
4. Write unit tests (25+ tests for edge cases)

**Files to create**:
- `backend/app/services/weight_redistribution.py`
- `backend/tests/unit/test_weight_redistribution.py`

### Step 5: Backend - Integrate with Watchlist Scoring
**File**: `backend/app/watchlist/watchlist_service.py`

1. Import security type and weight redistribution services
2. In `calculate_watchlist_scores()`:
   ```python
   # After fetching symbol
   security_type = security_type_service.detect_security_type(symbol)
   scoring_rules = scoring_rules_config.get_rules(security_type)

   # Calculate per-pillar scores (may skip some sub-components)
   pillar_scores = {}
   for pillar_name, pillar_config in scoring_rules.pillars.items():
       if not pillar_config.enabled:
           pillar_scores[pillar_name] = None
           continue

       if pillar_config.enabled == 'partial':
           pillar_scores[pillar_name] = calculate_pillar_score(
               symbol, pillar_name,
               exclude=pillar_config.exclude_metrics
           )
       else:
           pillar_scores[pillar_name] = calculate_pillar_score(symbol, pillar_name)

   # Redistribute weights
   applicability = [1 if score is not None else 0 for score in pillar_scores.values()]
   adjusted_weights = weight_redistributor.calculate_adjusted_weights(
       original_weights=scoring_rules.get_weights(),
       applicability=applicability
   )

   # Calculate final score
   final_score = sum(
       score * weight
       for score, weight in zip(pillar_scores.values(), adjusted_weights)
       if score is not None
   )
   ```
3. Store in `raw_metrics`:
   - `security_type`
   - `applicable_pillars`
   - `weight_adjustments`
   - `pillar_scores` (with weights)
4. Update response model

**Files to modify**:
- `backend/app/watchlist/watchlist_service.py` (~100 lines modified)
- `backend/app/api/watchlist.py` (WatchlistItemResponse model)

### Step 6: Frontend - TypeScript Types
**File**: `frontend/lib/api/watchlist.ts`

1. Add security type to `WatchlistItem`:
   ```typescript
   interface WatchlistItem {
     symbol: string;
     security_type: 'stock' | 'etf' | 'other';
     current_score: number;
     score_breakdown: {
       [pillarName: string]: {
         score: number;
         weight: number;
         original_weight: number;
         partial?: boolean;
       };
     };
     // ... other fields
   }
   ```

**Files to modify**:
- `frontend/lib/api/watchlist.ts`

### Step 7: Frontend - Security Type Badge
**File**: `frontend/components/watchlist/SecurityTypeBadge.tsx` (new)

1. Create small badge component showing security type
2. Style: ETF = blue, Stock = green, Other = gray
3. Optional icon (📊 for ETF, 📈 for stock)

**Files to create**:
- `frontend/components/watchlist/SecurityTypeBadge.tsx`

### Step 8: Frontend - Score Breakdown Tooltip Enhancement
**File**: `frontend/components/watchlist/ScoreBreakdownTooltip.tsx`

1. Show adjusted weights in tooltip
2. Add explanation: "Weights adjusted for ETF (no earnings data)"
3. Show which pillars are partial/excluded
4. Format:
   ```
   Technical: 85 (30.5% ↑ from 25%)
   Fundamental: 70 (15.2% ↓ from 25%, partial)
   Catalyst: 65 (14.6% ↓ from 20%, partial)
   Options: 80 (18.3% ↑ from 15%)
   Price: 75 (18.3% ↑ from 15%)

   ℹ️ Weights adjusted for ETF - fundamental and catalyst pillars partially applicable
   ```

**Files to modify**:
- `frontend/components/watchlist/ScoreBreakdownTooltip.tsx` (~30 lines)

### Step 9: Testing

#### Backend Tests
```bash
# Security type detection
cd ~/portfolio-ai/backend
pytest tests/unit/test_security_type_service.py -v

# Weight redistribution
pytest tests/unit/test_weight_redistribution.py -v

# Watchlist scoring with ETFs
pytest tests/integration/test_watchlist_api.py -v -k etf

# Full test suite
pytest tests/ -v
```

#### Manual Testing
1. Add ETF to watchlist: `SPY`, `QQQ`, `IWM`
2. Add stock to watchlist: `AAPL`, `MSFT`
3. Trigger refresh: `curl -X POST http://localhost:8000/api/watchlist/refresh`
4. Verify:
   - [ ] ETF scores exclude irrelevant metrics
   - [ ] Weights redistributed correctly
   - [ ] Score breakdown shows adjustments
   - [ ] Security type badge appears
   - [ ] Tooltip explains adjustments
   - [ ] Scores are comparable (0-100 scale)

#### Edge Cases to Test
- [ ] Unknown security type (defaults to 'stock')
- [ ] All pillars excluded (should handle gracefully)
- [ ] Partial pillar with all sub-metrics excluded
- [ ] Weight redistribution sums to 1.0 (no rounding errors)
- [ ] Mixed watchlist (stocks + ETFs)

### Step 10: Documentation
Update documentation:
- [ ] `docs/core/API_REFERENCE.md` (scoring endpoint response changes)
- [ ] `docs/core/ARCHITECTURE.md` (security-type-aware scoring design)
- [ ] `docs/core/DEVELOPMENT.md` (adding new security types, modifying rules)
- [ ] `backend/app/config/scoring_rules.yaml` (inline comments explaining rules)

### Step 11: Evidence Capture
```bash
# Capture ETF scoring
curl -s -X POST "http://localhost:8000/api/artifacts/refresh" \
  -H "Content-Type: application/json" \
  -d '{"feature_id": "FEAT-XXX", "criterion_id": "ac-001", "url": "http://192.168.8.233:3000/watchlist"}'
```

## Files Likely to Change

### Database
- `backend/app/storage/schema.sql` (~10 lines)
- `backend/migrations/XXX_add_security_type.sql` (new, ~30 lines)

### Backend (New)
- `backend/app/services/security_type_service.py` (new, ~150 lines)
- `backend/app/services/weight_redistribution.py` (new, ~120 lines)
- `backend/app/config/scoring_rules.yaml` (new, ~80 lines)
- `backend/app/config/scoring_rules.py` (new, ~100 lines)
- `backend/tests/unit/test_security_type_service.py` (new, ~200 lines)
- `backend/tests/unit/test_weight_redistribution.py` (new, ~300 lines)

### Backend (Modified)
- `backend/app/watchlist/watchlist_service.py` (~100 lines modified)
- `backend/app/api/watchlist.py` (~20 lines modified)

### Frontend (New)
- `frontend/components/watchlist/SecurityTypeBadge.tsx` (new, ~50 lines)

### Frontend (Modified)
- `frontend/lib/api/watchlist.ts` (~30 lines added)
- `frontend/components/watchlist/ScoreBreakdownTooltip.tsx` (~30 lines modified)
- `frontend/components/watchlist/WatchlistTable.tsx` (~10 lines modified to add badge)

### Documentation
- `docs/core/API_REFERENCE.md`
- `docs/core/ARCHITECTURE.md`
- `docs/core/DEVELOPMENT.md`

## Dependencies

- yfinance API (for security type detection)
- Existing watchlist scoring system
- `symbols` table in database

## Known Considerations

### Security Type Detection Accuracy
- yfinance may not always correctly identify ETFs vs stocks
- Need manual override mechanism for edge cases
- Consider maintaining whitelist of known ETFs

### Weight Redistribution Edge Cases
- What if all pillars are N/A? (Shouldn't happen, but handle gracefully)
- Rounding errors accumulating (ensure weights sum to exactly 1.0)
- Negative weights (impossible mathematically, but add assertion)

### Performance Impact
- Security type detection adds 1 DB query per symbol
- Batch detection reduces overhead
- Cache aggressively (security type rarely changes)

### Future Security Types
Architecture should support adding:
- Mutual funds
- Options
- Bonds
- Cryptocurrencies
- Commodities

### Backward Compatibility
- Existing scores should remain valid
- Default to 'stock' for unknown securities
- API response remains compatible (adds fields, doesn't break existing)

## Future Enhancements

### Phase 2: ETF-Specific Metrics
Add scoring for ETF-specific attributes:
- Expense ratio: Lower is better (0-10 score)
- AUM: Higher is better for liquidity (0-10 score)
- Tracking error: Lower is better (0-10 score)
- Holdings diversification: More is better (0-10 score)
- Distribution yield: Higher may be better (0-10 score)

### Phase 3: Sector/Industry-Specific Scoring
Different weights for different sectors:
- Tech stocks: Weight technical analysis higher
- Financial stocks: Weight fundamental analysis higher
- Biotech stocks: Weight catalyst events higher

### Phase 4: Time-of-Day Weighting
Adjust pillar weights based on market hours:
- Pre-market: Weight news/catalyst higher
- Intraday: Weight price action/technical higher
- After-hours: Weight options flow higher

## References

- Watchlist scoring: `backend/app/watchlist/watchlist_service.py`
- yfinance security type: `https://github.com/ranaroussi/yfinance#quote-type`
- Weight redistribution algorithm: `https://en.wikipedia.org/wiki/Normalization_(statistics)`
- ETF characteristics: `https://www.investopedia.com/terms/e/etf.asp`

## Success Criteria

**Feature is complete when**:
1. ✅ Database has `security_type` column populated
2. ✅ Backend detects security type accurately (>95% accuracy)
3. ✅ Pillar applicability rules loaded from config
4. ✅ Weight redistribution works mathematically (sums to 1.0)
5. ✅ ETF scores exclude inappropriate metrics
6. ✅ Watchlist API returns security type and adjusted weights
7. ✅ Frontend displays security type badge
8. ✅ Score breakdown tooltip shows weight adjustments
9. ✅ All tests pass (backend + frontend)
10. ✅ Documentation updated
11. ✅ Evidence captured and verified

---

**Priority**: High (improves scoring accuracy and transparency)
**Effort**: MEDIUM (algorithmic complexity, multiple touch points)
