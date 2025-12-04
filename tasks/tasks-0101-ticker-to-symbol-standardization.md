# Task List: Complete ticker→symbol Standardization

**Source**: User request via /task_it - CLAUDE.md mandates "NEVER use ticker"
**Complexity**: Complex (pattern replacement across entire codebase)
**Effort**: HIGH
**Environment**: Local Dev
**Created**: 2025-12-04 17:00
**Completed**: 2025-12-04 17:35

---

## Summary

**Goal**: Eliminate ALL instances of "ticker" in the codebase (variable names, function parameters, dict keys, comments, docstrings) and replace with "symbol" per CLAUDE.md standardization rules.

**Status**: ✅ COMPLETED

**Work Done**:
1. Fixed 8 critical bugs in app code (undefined variable references, wrong field names)
2. Updated 6 test files with ticker→symbol changes
3. Verified 92+ tests pass in the modified files
4. All application code now uses "symbol" consistently

**Remaining Legitimate "ticker" References**:
- `yf.Ticker()` - external yfinance library (cannot change)
- External API templates (Polygon, NASDAQ RSS) that use `{ticker}` in URLs
- Request builders that map `symbol` value to both `ticker` and `symbol` params for external APIs
- Comments in SEC CIK fetcher about "ticker→CIK mapping" (external API terminology)

---

## Completed Tasks

### Application Code Fixes (All ✅)

- [x] `backend/app/watchlist/fundamentals.py:91-92` - Fixed: `symbol = yf.Ticker(symbol)` then `yf_obj.info`
- [x] `backend/app/watchlist/earnings.py:45-46` - Fixed: `yf_obj = yf.Ticker(symbol)` then `yf_obj.calendar`
- [x] `backend/app/portfolio/manager.py:279` - Fixed: SQL insert uses `symbol` variable
- [x] `backend/app/utils/health_service.py:251` - Fixed: `symbol=item.symbol` field assignment
- [x] `backend/app/analytics/stress_testing.py:231` - Fixed: `symbol=symbol` in PositionStressResult
- [x] `backend/app/analytics/market_breadth.py:85` - Fixed: SQL SELECT uses `symbol` column
- [x] `backend/app/api/news.py:236` - Fixed: `symbol=symbol` parameter in service call
- [x] `backend/app/utils/task_locks.py:23` - Fixed: docstring example uses `symbol`
- [x] `backend/app/services/catalyst_scoring.py:193` - Fixed: docstring param name
- [x] `backend/app/watchlist/refresh_processor.py:80` - Fixed: docstring
- [x] `backend/app/watchlist/signal_classifier.py:272` - Fixed: docstring
- [x] `backend/app/watchlist/scoring_service/aggregator.py:72` - Fixed: comment
- [x] `backend/app/backtest/benchmark.py:95` - Fixed: docstring

### Test File Fixes (All ✅)

- [x] `tests/analytics/test_earnings_surprise.py` - Updated dataclass fields and dict keys
- [x] `tests/analytics/test_institutional_ownership.py` - Updated `.symbol` assertions
- [x] `tests/analytics/test_momentum.py` - Updated MomentumMetrics `symbol=` parameter
- [x] `tests/analytics/test_sector_strength.py` - Updated import name and mock data
- [x] `tests/analytics/test_trade_calculations.py` - Updated function name import
- [x] `tests/unit/analytics/test_volume.py` - Updated `min_symbols` and dict keys

### Verification (All ✅)

- [x] All modified test files pass (31/31 in sector_strength + volume, 92+ total)
- [x] Frontend verified clean (zero "ticker" instances in source)
- [x] Database columns already standardized (migrations 059, 060, 062)

---

## Not Changed (Intentionally)

These are **legitimate** external API references that cannot be changed:

1. **External API Field Mappings** (api-sources-registry.yaml)
   - Polygon, EODHD, Fidelity, FMP APIs use "ticker" in their actual responses

2. **URL Templates for External APIs** (rss_source.py, request_builders.py)
   - `{ticker}` template variable for external API URLs
   - Request builders provide both `ticker` and `symbol` for compatibility

3. **SEC CIK Fetcher Comments**
   - "ticker→CIK mapping" refers to external SEC terminology

4. **yfinance Library**
   - `yf.Ticker()` is the external library class name

---

## Resume Command

```bash
# Task completed - no resume needed
```
