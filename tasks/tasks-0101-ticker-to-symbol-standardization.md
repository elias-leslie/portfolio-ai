# Task List: Complete ticker→symbol Standardization

**Source**: User request via /task_it - CLAUDE.md mandates "NEVER use ticker"
**Complexity**: Complex (pattern replacement across entire codebase)
**Effort**: HIGH
**Environment**: Local Dev
**Created**: 2025-12-04 17:00

---

## Summary

**Goal**: Eliminate ALL instances of "ticker" in the codebase (variable names, function parameters, dict keys, comments, docstrings) and replace with "symbol" per CLAUDE.md standardization rules.

**Approach**:
1. Run very thorough discovery to find ALL remaining instances
2. Categorize by type (variable, parameter, comment, yfinance object, etc.)
3. Apply careful sed replacements with verification after each step
4. Preserve yf.Ticker() and Ticker( external library references
5. Run lint and tests to verify no corruption

**Scope Discovery**: REQUIRED - partial work already done, need to find remaining instances

**CRITICAL RULES**:
- NEVER replace `yf.Ticker` or `Ticker(` (external yfinance library)
- ALWAYS verify counts before/after each replacement
- DO NOT introduce corruption - verify syntax after each batch
- Run ruff check after each major replacement to catch errors early

---

## Tasks

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Run comprehensive grep to count ALL remaining "ticker" instances
  - Command: `grep -rn --include="*.py" "ticker" backend/app | grep -v __pycache__ | grep -v migrations | grep -v "yf.Ticker\|Ticker(" | wc -l`
  - Goal: Get exact count of remaining instances to fix
  - Output: Total count and breakdown by pattern type

- [ ] 0.2 Categorize remaining instances by type
  - Count: Comments/docstrings containing "ticker"
  - Count: Variable names (e.g., `ticker =`, `for ticker in`)
  - Count: Function/method names containing "ticker"
  - Count: String literals `"ticker"`
  - Count: Dict key access patterns
  - Count: yfinance object method calls (ticker.info, ticker.calendar - need special handling)

- [ ] 0.3 Create detailed replacement plan
  - List each pattern type with exact sed command
  - Specify order of operations (safest first)
  - Note any patterns requiring manual review

- [ ] 0.4 Checkpoint: Confirm scope before proceeding
  - Total instances remaining: [TBD]
  - Patterns to fix: [TBD]
  - Estimated effort: [TBD]

**DO NOT PROCEED TO TASK 1 UNTIL SCOPE CONFIRMED**

---

### 1.0 Fix Remaining Variable Names

- [ ] 1.1 Replace standalone `ticker` variable assignments
  - Pattern: `ticker =` → `symbol =` (already partially done)
  - Verify count before: `grep -c "ticker =" backend/app/**/*.py`
  - Apply replacement
  - Verify count after (should be 0)

- [ ] 1.2 Replace remaining loop variables
  - Pattern: `for ticker in` (already partially done, verify completion)
  - Verify and fix any remaining

- [ ] 1.3 Run ruff check to verify no syntax errors introduced
  - Command: `ruff check backend/app --select=E,F`

---

### 2.0 Fix yfinance Object Variable Names

**CRITICAL**: yfinance Ticker objects need special handling - rename the VARIABLE not the method calls

- [ ] 2.1 Identify yfinance Ticker object patterns
  - Find: `ticker = yf.Ticker(...)` patterns
  - These should become: `yf_obj = yf.Ticker(...)` or `yf_data = yf.Ticker(...)`

- [ ] 2.2 Replace yfinance object variable names
  - Pattern: Where `ticker` holds a yf.Ticker() object
  - Change variable name to `yf_obj` or `yf_data` (NOT `symbol`)
  - Update all references: `ticker.info` → `yf_obj.info`, etc.

- [ ] 2.3 Verify yfinance calls still work
  - Run quick test: `python -c "import yfinance as yf; t = yf.Ticker('AAPL'); print(t.info.get('symbol'))"`

---

### 3.0 Fix Comments and Docstrings

- [ ] 3.1 Replace "ticker" in docstrings
  - Pattern: `Stock ticker` → `Stock symbol`
  - Pattern: `a ticker` → `a symbol`
  - Pattern: `the ticker` → `the symbol`
  - Pattern: `ticker's` → `symbol's`

- [ ] 3.2 Replace "ticker" in inline comments
  - Same patterns as above
  - Be careful not to break code

- [ ] 3.3 Verify no code was accidentally modified
  - Run: `ruff check backend/app`

---

### 4.0 Fix Function and Class Names

- [ ] 4.1 Identify functions/methods with "ticker" in name
  - Find: `def.*ticker`, `async def.*ticker`
  - List all and determine if rename needed

- [ ] 4.2 Rename functions (if needed)
  - Update function definitions
  - Update ALL call sites
  - This may require careful manual review

- [ ] 4.3 Verify all imports and calls still work
  - Run: `ruff check backend/app`

---

### 5.0 Fix Remaining String Literals and Dict Keys

- [ ] 5.1 Find remaining `"ticker"` string literals
  - Exclude: External API field mappings (e.g., Polygon API returns "ticker")
  - Fix: Internal dict keys, log messages, etc.

- [ ] 5.2 Apply remaining replacements
  - Be conservative - verify each pattern

- [ ] 5.3 Run comprehensive lint check
  - Command: `~/portfolio-ai/scripts/lint.sh`

---

### 6.0 Database Verification

- [ ] 6.1 Verify database columns use "symbol" not "ticker"
  - Query: `SELECT column_name, table_name FROM information_schema.columns WHERE column_name LIKE '%ticker%'`
  - Should return empty (migrations already renamed columns)

- [ ] 6.2 Verify no SQL queries reference "ticker" column
  - Grep for SQL with ticker column references
  - Fix any found

---

### 7.0 Frontend Verification

- [ ] 7.1 Check TypeScript/JavaScript files for "ticker"
  - Command: `grep -rn "ticker" frontend/lib frontend/components frontend/app | grep -v node_modules`
  - Categorize and fix as needed

- [ ] 7.2 Verify frontend builds
  - Command: `cd frontend && npm run build`

---

### 8.0 Final Verification

- [ ] 8.1 Run final grep - should find ONLY yf.Ticker/Ticker( references
  - Command: `grep -rn --include="*.py" "ticker" backend/app | grep -v __pycache__ | grep -v migrations | grep -v "yf.Ticker\|Ticker("`
  - Expected: 0 results (or only acceptable exceptions)

- [ ] 8.2 Run full lint suite
  - Command: `~/portfolio-ai/scripts/lint.sh`
  - All checks must pass

- [ ] 8.3 Run pytest to verify no regressions
  - Command: `cd backend && pytest tests/ -x -q`
  - All tests must pass

- [ ] 8.4 Restart services and verify API works
  - Command: `bash ~/portfolio-ai/scripts/restart.sh`
  - Test: `curl http://localhost:8000/api/market/conditions | jq '.sp500.price'`
  - Should return actual price, not 0

- [ ] 8.5 Commit all changes
  - Message: "refactor: Complete ticker→symbol standardization per CLAUDE.md"

---

## Verification Checklist

- [ ] Functional: All APIs return correct data (not 0.0)
- [ ] Tests: All pytest tests pass
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes (ruff + mypy)
- [ ] Services: Restarted and verified working
- [ ] Clean: No "ticker" except yf.Ticker/Ticker( external library
- [ ] Docs: CLAUDE.md rules followed

---

## Resume Command

```bash
/do_it tasks/tasks-0101-ticker-to-symbol-standardization.md
```
