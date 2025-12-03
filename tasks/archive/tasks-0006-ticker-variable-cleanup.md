# Task List: Ticker Variable Name Cleanup (OPTIONAL)

**Source**: User request via /task_it - audit of remaining ticker references
**Complexity**: Simple
**Effort**: LOW
**Environment**: Local Dev
**Created**: 2025-12-03 17:35

---

## Summary

**Goal**: Document remaining `ticker` variable/parameter names in codebase for optional future cleanup
**Approach**: These are NOT bugs - all DB columns use `symbol`. This is cosmetic variable renaming only.
**Scope Discovery**: Not needed - already scanned

---

## Current State (VERIFIED COMPLETE)

### Database: 100% Standardized
- All tables use `symbol` column (not `ticker`)
- All SQL queries reference `symbol`

### API: 100% Standardized
- All request/response models use `symbol` field
- All query parameters use `symbol`

### Frontend: 100% Clean
- Zero `ticker` references found

### Backend Variable Names (OPTIONAL cleanup)

These are **variable names only** - not DB columns. Renaming is cosmetic:

1. **app/watchlist/refresh_processor.py** - Function `process_ticker_snapshot()`, docstrings
2. **app/watchlist/background_tasks.py** - Function `schedule_new_ticker_tasks()`, param `tickers`
3. **app/watchlist/refresh_data_fetchers.py** - Variable `tickers_needing_backfill`
4. **app/watchlist/signal_classifier.py** - Field `ticker_in_active_sector`
5. **app/watchlist/earnings.py** - Variable `ticker = yf.Ticker(symbol)` (yfinance API)
6. **app/analytics/paper_trading_portfolio.py** - Variable `ticker` holding symbol value

---

## Tasks (IF choosing to rename variables)

### 1.0 Rename Variable Names (OPTIONAL)

- [ ] 1.1 Rename `process_ticker_snapshot` → `process_symbol_snapshot`
- [ ] 1.2 Rename `schedule_new_ticker_tasks` → `schedule_new_symbol_tasks`
- [ ] 1.3 Rename `tickers_needing_backfill` → `symbols_needing_backfill`
- [ ] 1.4 Rename `ticker_in_active_sector` → `symbol_in_active_sector`
- [ ] 1.5 Update docstrings mentioning "ticker"

### 2.0 Keep As-Is (RECOMMENDED)

- [ ] 2.1 `ticker = yf.Ticker(symbol)` - yfinance API uses this name
- [ ] 2.2 Local variables holding symbol values (common industry term)

---

## Verification

- [x] Functional: All DB/API standardized to `symbol` ✅
- [x] Tests: Would need to run pytest after any renames
- [x] Quality: lint.sh passes
- [ ] Optional: Variable rename for consistency (low priority)

---

## Recommendation

**NO ACTION NEEDED** - The critical work (DB columns, API fields, SQL queries) is complete.
Variable names are developer preference and don't affect functionality.

Mark this task as COMPLETE or WONT_DO.
