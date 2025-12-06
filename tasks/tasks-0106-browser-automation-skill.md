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
- [ ] screenshot.js - Basic screenshot
- [ ] console.js - Console capture
- [ ] interact.js - Click testing
- [ ] execute.js - JavaScript execution
- [ ] snapshot.js - Accessibility tree
- [ ] network.js - Network capture
- [ ] performance.js - Performance metrics
- [ ] manage.js - Multi-page
- [ ] emulate.js - Device emulation

---

## Phase 1: Fix Core Scripts

### 1.1 screenshot.js Improvements

- [ ] 1.1.1 Add `--wait-for-idle` option (wait for network idle)
- [ ] 1.1.2 Add `--wait-for-selector` option (wait for specific element)
- [ ] 1.1.3 Add retry logic on timeout
- [ ] 1.1.4 Document all options with examples

**Current usage**:
```bash
node screenshot.js <url> <output> [fullPage]
```

**Proposed usage**:
```bash
node screenshot.js <url> <output> [options]
# Options: --full, --wait-idle, --wait-for="selector", --delay=1000
```

### 1.2 interact.js Improvements

- [ ] 1.2.1 Fix tab clicking for React components
- [ ] 1.2.2 Add `--wait-before` and `--wait-after` options
- [ ] 1.2.3 Add retry logic for flaky clicks
- [ ] 1.2.4 Support role-based selectors (getByRole)
- [ ] 1.2.5 Document reliable selector patterns

**Current issues**:
- `click button[value="features"]` times out
- Tab components need text-based selection

**Fix approach**:
```javascript
// Instead of: page.click('button[value="features"]')
// Use: page.getByRole('tab', { name: /Features/i }).click()
```

### 1.3 execute.js Improvements

- [ ] 1.3.1 Add async/await support properly
- [ ] 1.3.2 Add `--screenshot-after` option
- [ ] 1.3.3 Better error messages on script failure
- [ ] 1.3.4 Document common patterns

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

- [ ] 2.3.1 Screenshot default tab (Dashboard)
- [ ] 2.3.2 Click each tab and screenshot:
  - [ ] Dashboard
  - [ ] Vision
  - [ ] Features
  - [ ] Sources
  - [ ] Rules
  - [ ] Database
  - [ ] Tasks
  - [ ] Endpoints
  - [ ] Gaps
  - [ ] Insights
- [ ] 2.3.3 Expand a feature row in Features tab
- [ ] 2.3.4 Expand a vision goal in Vision tab
- [ ] 2.3.5 Use filters (category, status, vision goal)
- [ ] 2.3.6 Document working commands for ALL interactions

### 2.4 Portfolio (`/portfolio`)

- [ ] 2.4.1 Screenshot portfolio view
- [ ] 2.4.2 Expand a holding row
- [ ] 2.4.3 Verify metrics visible
- [ ] 2.4.4 Document working commands

### 2.5 Trading (`/trading`)

- [ ] 2.5.1 Screenshot trading view
- [ ] 2.5.2 Expand order details
- [ ] 2.5.3 Navigate tabs (if any)
- [ ] 2.5.4 Document working commands

### 2.6 Backtest (`/backtest`)

- [ ] 2.6.1 Screenshot backtest list
- [ ] 2.6.2 Click a backtest to see details
- [ ] 2.6.3 Verify charts render
- [ ] 2.6.4 Document working commands

### 2.7 Other Pages

- [ ] 2.7.1 Strategies - basic screenshot + interactions
- [ ] 2.7.2 Recommendations - basic screenshot + expand
- [ ] 2.7.3 Agents - screenshot + verify charts
- [ ] 2.7.4 Status - screenshot + verify indicators
- [ ] 2.7.5 Settings - screenshot + toggle test

---

## Phase 3: Create Unified Testing Script

### 3.1 Create test-all-pages.js

- [ ] 3.1.1 Loop through all pages
- [ ] 3.1.2 Screenshot each with standardized naming
- [ ] 3.1.3 Collect console errors
- [ ] 3.1.4 Generate summary report
- [ ] 3.1.5 Fail if any page has errors

### 3.2 Create tab-interaction.js

- [ ] 3.2.1 Generic tab clicking helper
- [ ] 3.2.2 Works with Radix UI tabs
- [ ] 3.2.3 Waits for content to load
- [ ] 3.2.4 Returns success/failure

### 3.3 Create expand-row.js

- [ ] 3.3.1 Generic row expansion helper
- [ ] 3.3.2 Works with table rows
- [ ] 3.3.3 Waits for expanded content
- [ ] 3.3.4 Screenshots before/after

---

## Phase 4: Documentation

### 4.1 Update Skill Documentation

- [ ] 4.1.1 Document every script with examples
- [ ] 4.1.2 Document selector patterns that work
- [ ] 4.1.3 Document common pitfalls
- [ ] 4.1.4 Add troubleshooting guide

### 4.2 Create Quick Reference

- [ ] 4.2.1 One-liner commands for each page
- [ ] 4.2.2 Tab click commands per page
- [ ] 4.2.3 Row expansion commands
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

## Appendix A: Known Working Commands (To Update)

```bash
# Dashboard screenshot
node screenshot.js http://192.168.8.233:3000/ /tmp/dashboard.png

# Console errors (5 seconds)
node console.js http://192.168.8.233:3000/capabilities 5000

# Click by text (RELIABLE)
node interact.js click http://192.168.8.233:3000/capabilities "text=Features"

# Execute JS and get content
node execute.js http://192.168.8.233:3000/capabilities "
  await new Promise(r => setTimeout(r, 2000));
  return document.body.innerText.substring(0, 3000);
"
```

## Appendix B: Selector Patterns That Work

| Component Type | Selector Pattern | Notes |
|---------------|------------------|-------|
| Radix Tab | `text=TabName` | Use interact.js click |
| Button | `button:has-text("Label")` | Works with Playwright |
| Table Row | `tr:has-text("FEAT-001")` | Find by content |
| Expandable | Click row, wait, screenshot | Multi-step |

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
