# Security-Type-Aware Scoring

**Implements**: FEAT-216
**Status**: planned
**Effort**: MEDIUM
**Priority**: P2

## Context

Current scoring applies all 5 pillars equally to all securities:
- Technical (25%), Fundamental (25%), Catalyst (15%), Options (10%), Price (25%)

Problem: ETFs don't have company-level fundamentals (P/E, margins). Scoring them on fundamentals is meaningless and skews comparisons.

Data Quality indicator already implements security-type-aware logic (FEAT completed) - this extends the same pattern to actual scoring.

## Approach

1. Detect security type from `symbols.security_type`
2. Define applicable pillars per type (same as DQ):
   - `equity`: all 5 pillars
   - `etf`: technical, options, price (exclude fundamental, catalyst)
3. Redistribute weights dynamically among applicable pillars
4. Include transparency in API response

## Files to Modify

- `backend/app/watchlist/scoring.py` - Add security-type weight adjustment
- `backend/app/watchlist/models.py` - Add weight_adjustments to response model
- `backend/app/watchlist/data_quality.py` - Reference APPLICABLE_PILLARS constant

## Steps

- [ ] Import APPLICABLE_PILLARS from data_quality.py or move to shared constants
- [ ] Update `calculate_watchlist_scores()` to check security_type
- [ ] Redistribute weights when pillars are excluded
- [ ] Add `weight_adjustments` field to score response showing original vs applied
- [ ] Update tests to verify ETF vs stock scoring

## Verification

- [ ] `curl /api/watchlist | jq '.items[] | select(.symbol=="QQQ") | .current_score'` shows 3-pillar weights
- [ ] `curl /api/watchlist | jq '.items[] | select(.symbol=="AAPL") | .current_score'` shows 5-pillar weights
- [ ] ETF overall scores are comparable to stock scores (not artificially lower)

## Rollback

If issues occur: `git reset --hard HEAD~1`
