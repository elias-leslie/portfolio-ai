# Task List: Data Architecture Fixes (from /data_check)

**Source**: /data_check analysis (2025-12-04)
**Complexity**: Simple (5 independent LOW effort fixes)
**Effort**: LOW-MEDIUM (total ~2-3 hours)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-12-04 15:30

---

## Summary

**Goal**: Address top 5 data architecture issues identified by /data_check analysis
**Approach**: Fix each issue independently - all are LOW effort, high impact DRY/normalization improvements
**Scope Discovery**: Required for tasks 2-5 (find all instances across codebase)

---

## Tasks

### 1.0 Add FK Constraints to Fundamental Tables (Migration 068)

**Issue**: No referential integrity for `cash_flow_metrics`, `insider_transactions`, `institutional_holdings`, `short_interest`
**Files**: `backend/migrations/068_fundamental_data_tables.sql`

- [ ] 1.1 Create migration 069 to add FK constraints
  ```sql
  ALTER TABLE cash_flow_metrics
  ADD CONSTRAINT fk_cash_flow_metrics_symbol
  FOREIGN KEY (symbol) REFERENCES symbols(symbol)
  ON UPDATE CASCADE ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;
  -- Repeat for insider_transactions, institutional_holdings, short_interest
  ```
- [ ] 1.2 Run migration and verify constraints applied
- [ ] 1.3 Test that inserts with invalid symbols are rejected

### 2.0 Extract Date Conversion Utility (DRY Fix)

**Issue**: ~240 lines of identical date conversion logic duplicated in 5 source files
**Files to update**:
- `backend/app/sources/yfinance_source.py:58-71`
- `backend/app/sources/finnhub_source.py:196-209`
- `backend/app/sources/alphavantage_source.py:194-207`
- `backend/app/sources/twelvedata_source.py:200-213`
- `backend/app/sources/fmp_source.py:192-205`

- [ ] 2.1 Scope Discovery: Verify exact locations of duplicate code
  - Pattern: `isinstance(request.start, dt.date)` date conversion blocks
  - Goal: Confirm all 5 files and exact line numbers
- [ ] 2.2 Create `standardize_dates()` utility in `backend/app/sources/base.py`
  ```python
  def standardize_dates(request: DatasetRequest) -> tuple[dt.date, dt.date]:
      """Convert request start/end to date objects."""
      # Consolidate the repeated logic here
  ```
- [ ] 2.3 Update all 5 source files to use the utility
- [ ] 2.4 Run tests to verify no regressions

### 3.0 Extract OHLCVBuilder Helper (DRY Fix)

**Issue**: ~280 lines of similar DataFrame creation logic across 4 API sources
**Files to update**:
- `backend/app/sources/finnhub_source.py:250-267`
- `backend/app/sources/alphavantage_source.py:246-267`
- `backend/app/sources/twelvedata_source.py:255-270`
- `backend/app/sources/fmp_source.py:240-255`

- [ ] 3.1 Scope Discovery: Analyze the 4 implementations
  - Pattern: Manual dict list → pl.DataFrame for OHLCV records
  - Goal: Identify common logic vs source-specific variations
- [ ] 3.2 Create `OHLCVBuilder` helper class in `backend/app/sources/ohlcv_builder.py`
  ```python
  class OHLCVBuilder:
      """Build standardized OHLCV DataFrames from API responses."""
      def __init__(self, source_name: str): ...
      def add_record(self, date, open, high, low, close, volume, ticker): ...
      def build(self) -> pl.DataFrame: ...
  ```
- [ ] 3.3 Update all 4 source files to use OHLCVBuilder
- [ ] 3.4 Run tests to verify no regressions

### 4.0 Create FREDClient with Connection Pooling

**Issue**: FRED source creates new HTTP session per request (inefficient)
**File**: `backend/app/sources/fred.py:97`

- [ ] 4.1 Create `FREDClient` class extending `BaseHTTPClient`
  ```python
  class FREDClient(BaseHTTPClient):
      def get_api_key_env_var(self) -> str: return "FRED_API_KEY"
      def get_client_name(self) -> str: return "FRED"
      def get_api_key_param_name(self) -> str: return "api_key"
  ```
- [ ] 4.2 Add singleton pattern (like other clients)
- [ ] 4.3 Update `fred.py` to use the persistent client
- [ ] 4.4 Verify FRED data fetching still works

### 5.0 Abstract API Error Response Checking (DRY Fix)

**Issue**: 4 implementations of similar error response checking logic
**Files to update**:
- `backend/app/sources/finnhub_source.py:233` - `response.get("s") == "no_data"`
- `backend/app/sources/twelvedata_source.py:239` - `response.get("status") == "error"`
- `backend/app/sources/alphavantage_source.py:222` - `"Error Message" in response`
- `backend/app/sources/fmp_source.py:224` - `"Error Message" in response`

- [ ] 5.1 Scope Discovery: Document exact error patterns per source
  - Finnhub: `s == "no_data"`
  - TwelveData: `status == "error"`
  - AlphaVantage: `"Error Message"` or `"Note"` in response
  - FMP: `"Error Message"` in response
- [ ] 5.2 Create `check_api_error()` method in `BaseHTTPClient`
  ```python
  def check_api_error(self, response: dict) -> str | None:
      """Override in subclass. Return error message if response indicates error."""
      return None  # Default: no error
  ```
- [ ] 5.3 Implement in each client subclass
- [ ] 5.4 Update source files to use the standardized method
- [ ] 5.5 Run tests to verify error handling unchanged

---

## Verification

- [ ] Functional: All 5 fixes applied, zero regressions
- [ ] Tests: All existing tests pass (`pytest tests/ -v`)
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes (ruff + mypy)
- [ ] Services: Restarted and verified (`bash ~/portfolio-ai/scripts/restart.sh`)
- [ ] Clean: No new code duplication introduced

---

## Notes

- All fixes are independent - can be done in any order
- Each fix is LOW effort (~20-30 min)
- Tasks 2, 3, 5 have mild scope discovery to confirm file locations
- Task 1 (FK constraints) is the highest impact/lowest effort - do first
