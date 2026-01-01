# Task List: Browser Automation Skill - Review, Test & Improve

**Source**: User request to ensure browser automation is reliable across all pages
**Complexity**: Medium
**Effort**: MEDIUM
**Environment**: Local Dev
**Created**: 2025-12-06

---

## Summary

**Goal**: Ensure the browser automation skill works reliably for ALL pages and interactions in the Portfolio AI app, with clear documentation so Claude Code can use it without fumbling.

**Current Issues Identified**:
- Tab clicking doesn't work reliably (capabilities page Vision tab)
- Selectors like `button[value="features"]` timeout when page loads slowly
- No consistent pattern for waiting for React hydration
- Screenshots sometimes show loading states
- Expanding rows/sections is fragile

**Target State**:
- Every page has verified working screenshot/interaction commands
- Documented selector patterns that work reliably
- Clear error handling and retry patterns
- All scripts have consistent timeout and wait patterns

---

## Phase 0: Inventory & Baseline Testing

### 0.1 Document All Pages

| Route | Page | Key Interactions | Priority |
|-------|------|------------------|----------|
| `/` | Dashboard | F&G gauge, sector cards, market summary | HIGH |
| `/watchlist` | Watchlist | Expand rows, sort columns, search | HIGH |
| `/portfolio` | Portfolio | Expand holdings, view metrics | HIGH |
| `/trading` | Paper Trading | Expand orders, view history | HIGH |
| `/backtest` | Backtest | Run list, expand details, charts | MEDIUM |
| `/strategies` | Strategies | Strategy cards, edit modal | MEDIUM |
| `/recommendations` | Recommendations | Rec cards, expand details | MEDIUM |
| `/capabilities` | Capabilities | 10 tabs, expand rows, filters | HIGH |
| `/agents` | Agents | Metrics, charts, tables | MEDIUM |
| `/status` | Status | Services, health indicators | MEDIUM |
| `/settings` | Settings | Form inputs, toggles | LOW |
| `/ideas/[id]` | Idea Detail | Dynamic route | LOW |

### 0.2 Baseline Test Each Script

For each script, run against `/` (dashboard) and record:
- [x] screenshot.js - Basic screenshot ✅
- [x] console.js - Console capture ✅
- [x] interact.js - Click testing ✅
- [x] execute.js - JavaScript execution ✅
- [x] snapshot.js - Accessibility tree ✅
- [x] network.js - Network capture ✅
- [x] performance.js - Performance metrics ✅
- [x] manage.js - Multi-page ✅
- [x] emulate.js - Device emulation ✅
- [x] expand-and-screenshot.js - Expand row + screenshot ✅

### 0.3 Verify Prerequisites

- [x] Playwright installed and chromium available ✅
- [x] Frontend running at http://192.168.8.233:3000 ✅
- [x] Backend services healthy ✅

---

## Phase 1: Fix Core Scripts

### 1.1 screenshot.js Improvements

- [ ] 1.1.1 Add `--wait-for-selector` option (wait for specific element before screenshot)
- [ ] 1.1.2 Add `--delay=<ms>` option (extra wait after page load)
- [ ] 1.1.3 Add retry logic on timeout
- [ ] 1.1.4 Document all options with examples

**Note:** Already uses `waitUntil: 'networkidle'` - no need to add that.

**Current usage**:
```bash
node screenshot.js <url> <output> [fullPage]
```

**Proposed usage**:
```bash
node screenshot.js <url> <output> [options]
# Options: --full, --wait-for="selector", --delay=1000
```

### 1.2 interact.js Improvements

- [ ] 1.2.1 Fix tab clicking for React/Radix UI components
- [ ] 1.2.2 Add `--wait-before` and `--wait-after` options
- [ ] 1.2.3 Add retry logic for flaky clicks
- [ ] 1.2.4 Document reliable selector patterns
- [ ] 1.2.5 Document Radix UI Tabs patterns (data-state, role="tab")

**Current issues**:
- `click button[value="features"]` times out
- Tab components need text-based selection

**Recommended selector strategy (use consistently):**
```bash
# PRIMARY: Use text= selector (simple, reliable)
node interact.js click http://... "text=Features"

# ALTERNATIVE: Use role selector for Radix tabs
node interact.js click http://... "[role='tab']:has-text('Features')"

# VERIFY: Check tab state after click
node execute.js http://... "document.querySelector('[data-state=\"active\"]')?.textContent"
```

### 1.3 execute.js Improvements

- [ ] 1.3.1 Document existing async/await patterns (already supported!)
- [ ] 1.3.2 Add `--screenshot-after` option
- [ ] 1.3.3 Better error messages on script failure
- [ ] 1.3.4 Document common patterns

**Note:** Async/await already works - code is wrapped in async function automatically.

### 1.4 console.js Improvements

- [ ] 1.4.1 Filter noise (React DevTools messages)
- [ ] 1.4.2 Add severity filtering (--errors-only)
- [ ] 1.4.3 Better formatting for long messages

---

## Phase 2: Page-Specific Test Suite

### 2.1 Dashboard (`/`)

- [ ] 2.1.1 Screenshot default view
- [ ] 2.1.2 Verify Fear & Greed gauge visible
- [ ] 2.1.3 Verify sector cards load
- [ ] 2.1.4 Check for console errors
- [ ] 2.1.5 Document working commands

### 2.2 Watchlist (`/watchlist`)

- [ ] 2.2.1 Screenshot with data loaded
- [ ] 2.2.2 Expand first stock row
- [ ] 2.2.3 Screenshot expanded state
- [ ] 2.2.4 Click column headers (sort)
- [ ] 2.2.5 Use search input
- [ ] 2.2.6 Document working commands

### 2.3 Capabilities (`/capabilities`)

- [x] 2.3.1 Screenshot default tab (Dashboard) ✅
- [x] 2.3.2 Click each tab and screenshot:
  - [x] Dashboard ✅
  - [x] Vision ✅
  - [x] Features ✅
  - [x] Sources ✅
  - [x] Rules ✅
  - [x] Database ✅
  - [x] Tasks ✅
  - [x] Endpoints ✅
  - [x] Gaps ✅
  - [x] Insights ✅
- [x] 2.3.3 Expand a feature row in Features tab ✅ (click first cell chevron)
- [x] 2.3.4 Expand a vision goal in Vision tab ✅ (same pattern)
- [ ] 2.3.5 Use filters (category, status, vision goal)
- [x] 2.3.6 Document working commands for ALL interactions ✅ (in Appendix A)

**Feature Row Expansion (verified):**
```javascript
// Click first cell (chevron) to expand - shows acceptance criteria
const firstRow = document.querySelector('tbody tr');
firstRow?.querySelector('td:first-child')?.click();
// Row count increases, expanded row shows "Acceptance Criteria (X/Y verified)"
```

### 2.4 Portfolio (`/portfolio`)

- [x] 2.4.1 Screenshot portfolio view ✅
- [ ] 2.4.2 Expand a holding row
- [x] 2.4.3 Verify metrics visible ✅
- [x] 2.4.4 Document working commands ✅ (in Appendix A)

### 2.5 Trading (`/trading`)

- [x] 2.5.1 Screenshot trading view ✅ (shows 7 open positions, $100K portfolio)
- [ ] 2.5.2 Expand order details
- [ ] 2.5.3 Navigate tabs (if any)
- [x] 2.5.4 Document working commands ✅ (in Appendix A)

### 2.6 Backtest (`/backtest`)

- [x] 2.6.1 Screenshot backtest list ✅
- [ ] 2.6.2 Click a backtest to see details
- [ ] 2.6.3 Verify charts render
- [ ] 2.6.4 Document working commands

### 2.7 Other Pages

- [x] 2.7.1 Strategies - basic screenshot ✅
- [x] 2.7.2 Recommendations - basic screenshot ✅
- [x] 2.7.3 Agents - screenshot ✅
- [ ] 2.7.4 Status - ⚠️ TIMES OUT (continuous polling prevents networkidle)
- [ ] 2.7.5 Settings - screenshot + toggle test

**Note:** /status page requires `domcontentloaded` instead of `networkidle` due to continuous health check polling.

---

## Phase 3: Create Unified Testing Script

### 3.1 Create test-all-pages.js

- [ ] 3.1.1 Loop through all pages
- [ ] 3.1.2 Screenshot each with standardized naming
- [ ] 3.1.3 Collect console errors
- [ ] 3.1.4 Generate summary report
- [ ] 3.1.5 Fail if any page has errors

### 3.2 Create tab-interaction.js → DONE: tab-click-screenshot.js

- [x] 3.2.1 Generic tab clicking helper ✅
- [x] 3.2.2 Works with Radix UI tabs ✅ (tested on /capabilities)
- [x] 3.2.3 Waits for content to load ✅ (configurable wait-ms)
- [x] 3.2.4 Returns success/failure ✅

### 3.3 Improve expand-and-screenshot.js (Already Exists!)

- [ ] 3.3.1 Make more generic (not just watchlist)
- [ ] 3.3.2 Add --wait-after option for slower content
- [ ] 3.3.3 Add --before-screenshot option (capture collapsed state)
- [ ] 3.3.4 Support different expand button patterns (not just first button)

---

## Phase 4: Documentation

### 4.1 Audit & Update SKILL.md (Already Comprehensive!)

**Note:** SKILL.md already has ~540 lines of documentation. Focus on gaps.

- [x] 4.1.1 Add page-specific selector patterns discovered in Phase 2 ✅
- [x] 4.1.2 Add Radix UI component patterns ✅ (Workflow 6)
- [x] 4.1.3 Update troubleshooting with real issues found ✅ (Known Issues table)
- [x] 4.1.4 Add "Known Working Commands" section per page ✅ (Workflow 6 examples)

### 4.2 Create Quick Reference

- [x] 4.2.1 One-liner commands for each page ✅ (Appendix A in task file)
- [x] 4.2.2 Tab click commands per page ✅ (SKILL.md Workflow 6)
- [x] 4.2.3 Row expansion commands ✅ (SKILL.md Workflow 5)
- [ ] 4.2.4 Common filter interactions

### 4.3 Update CLAUDE.md

- [ ] 4.3.1 Add browser automation quick reference section
- [ ] 4.3.2 Link to full documentation

---

## Phase 5: Integration Tests

### 5.1 Add to /fix_it or /test_it

- [ ] 5.1.1 Run browser automation suite
- [ ] 5.1.2 Report failures clearly
- [ ] 5.1.3 Take screenshots of failures

### 5.2 CI Integration (Optional)

- [ ] 5.2.1 Add GitHub Action for browser tests
- [ ] 5.2.2 Run on PR to frontend

---

## Appendix A: Known Working Commands (VERIFIED 2025-12-06)

```bash
# All scripts located at: ~/portfolio-ai/.claude/skills/browser-automation/scripts/

# === SCREENSHOTS ===
node screenshot.js http://192.168.8.233:3000/ /tmp/dashboard.png true
node screenshot.js http://192.168.8.233:3000/portfolio /tmp/portfolio.png true
node screenshot.js http://192.168.8.233:3000/trading /tmp/trading.png true

# === TAB CLICK + SCREENSHOT (SAME SESSION - USE THIS FOR TABS!) ===
node tab-click-screenshot.js http://192.168.8.233:3000/capabilities Vision /tmp/vision.png 2000
node tab-click-screenshot.js http://192.168.8.233:3000/capabilities Features /tmp/features.png 2000
node tab-click-screenshot.js http://192.168.8.233:3000/capabilities Database /tmp/database.png 2000

# === EXPAND ROW + SCREENSHOT ===
node expand-and-screenshot.js http://192.168.8.233:3000/watchlist AAPL /tmp/aapl-expanded.png

# === CONSOLE CAPTURE ===
node console.js http://192.168.8.233:3000/ 3000
node console.js http://192.168.8.233:3000/capabilities 5000

# === CLICK INTERACTIONS ===
node interact.js click http://192.168.8.233:3000/ "text=Watchlist"
node interact.js click http://192.168.8.233:3000/capabilities "text=Features"

# === JAVASCRIPT EXECUTION ===
node execute.js http://192.168.8.233:3000/ "return document.title"
node execute.js http://192.168.8.233:3000/capabilities "
  const tabs = Array.from(document.querySelectorAll('button')).filter(b => b.textContent?.includes('Vision'));
  tabs[0]?.click();
  await new Promise(r => setTimeout(r, 1500));
  return document.body.innerText.substring(0, 2000);
"

# === NETWORK MONITORING ===
node network.js http://192.168.8.233:3000/ 3000 api

# === PERFORMANCE METRICS ===
node performance.js metrics http://192.168.8.233:3000/ /tmp/perf.json

# === DEVICE EMULATION ===
node emulate.js resize http://192.168.8.233:3000/ 375 667

# === PAGE MANAGEMENT ===
node manage.js new http://192.168.8.233:3000/watchlist
node manage.js list
```

## Appendix B: Selector Patterns That Work

| Component Type | Selector Pattern | Notes |
|---------------|------------------|-------|
| Radix Tab | `text=TabName` | PRIMARY - simple and reliable |
| Radix Tab (alt) | `[role='tab']:has-text('Name')` | More specific |
| Radix Tab State | `[data-state='active']` | Check which tab is active |
| Button | `button:has-text("Label")` | Works with Playwright |
| Table Row | `tr:has-text("FEAT-001")` | Find by content |
| Expandable | Click row, wait, screenshot | Multi-step |
| Radix Accordion | `[data-state='open']` | Check expansion state |
| Shadcn Select | `[role='combobox']` | Dropdown triggers |

## Appendix C: Wait Patterns

```javascript
// Wait for network idle
await page.waitForLoadState('networkidle');

// Wait for specific element
await page.waitForSelector('[data-testid="loaded"]');

// Wait for React hydration
await page.waitForTimeout(2000); // Fallback

// Wait for no loading spinners
await page.waitForSelector('.loading', { state: 'hidden' });
```

---

**Version**: 1.0.0 | **Created**: 2025-12-06
