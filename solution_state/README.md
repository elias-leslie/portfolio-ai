# Solution State

UI regression test captures and verification artifacts.

---

## Purpose

This folder stores timestamped snapshots of the UI state for:
- **Regression testing**: Compare current state against baseline
- **Documentation**: Visual proof of feature completion
- **Debugging**: Console errors, network failures, page state
- **History**: Track UI changes over time

---

## Folder Structure

```
solution_state/
├── README.md                    # This file
├── YYYYMMDD-HHMMSS/            # Timestamped capture folders
│   ├── REPORT.md               # Summary report
│   ├── pages/                  # All 9 pages
│   │   ├── {page}.png          # Screenshot
│   │   └── {page}.json         # Console, network, page state
│   ├── tabs/                   # All 12 tab variations
│   │   ├── {page}-tab-{tab}.png
│   │   └── {page}-tab-{tab}.json
│   ├── expanded/               # Expanded row captures
│   │   ├── {page}-expanded-{id}.png
│   │   └── {page}-expanded-{id}.json
│   └── mobile/                 # Mobile viewport captures
│       └── {page}.png
└── ...                         # Additional capture folders
```

---

## How to Create New Captures

### Full Suite (Recommended)

```bash
/test_it --full
```

Captures all pages, tabs, expanded sections, and mobile views.

### Specific Categories

```bash
/test_it --pages      # All 9 pages only
/test_it --tabs       # All 12 tab variations
/test_it --expanded   # Expanded sections
/test_it --mobile     # Mobile viewports
/test_it --quick      # Dashboard + Watchlist basics
```

### Manual Capture

```bash
SCRIPT_DIR="$HOME/portfolio-ai/.claude/skills/browser-automation/scripts"
OUTPUT_DIR="$HOME/portfolio-ai/solution_state/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUTPUT_DIR"/{pages,tabs,expanded,mobile}

# Single page
node "$SCRIPT_DIR/regression-check.js" http://192.168.8.233:3000/watchlist "$OUTPUT_DIR/pages"

# With tab click
node "$SCRIPT_DIR/regression-check.js" http://192.168.8.233:3000/capabilities "$OUTPUT_DIR/tabs" --click-tab "Features"

# With row expansion
node "$SCRIPT_DIR/regression-check.js" http://192.168.8.233:3000/watchlist "$OUTPUT_DIR/expanded" --expand-row "AAPL"

# Mobile
node "$SCRIPT_DIR/emulate.js" device http://192.168.8.233:3000/watchlist "iPhone 12 Pro" "$OUTPUT_DIR/mobile/watchlist.png"
```

---

## Capture Coverage

### Pages (9)

| Page | URL | Content |
|------|-----|---------|
| Dashboard | `/` | Market Intelligence, News |
| Watchlist | `/watchlist` | Ticker table, sparklines |
| Portfolio | `/portfolio` | Account data |
| Trading | `/trading` | Open/closed positions |
| Backtest | `/backtest` | Run history |
| Agents | `/agents` | Telemetry charts |
| Status | `/status` | Health checks |
| Capabilities | `/capabilities` | Feature registry |
| Settings | `/settings` | Config forms |

### Tabs (12)

| Page | Tabs |
|------|------|
| Capabilities | Dashboard, Vision, Features, Workflows, Sources, Rules, DB, Log, Tasks, API |
| Trading | Open Positions, Closed Trades |

### Expanded Sections

| Page | Expansion |
|------|-----------|
| Watchlist | Ticker rows (score breakdown, news, trade levels) |
| Trading | Trade rows |
| Capabilities/Features | Feature rows |
| Portfolio | Account/Position |

### Mobile Views (7)

All pages except backtest and agents (complex charts).

---

## JSON Report Format

Each `.json` file contains:

```json
{
  "success": true,
  "url": "http://192.168.8.233:3000/watchlist",
  "pageName": "watchlist",
  "interaction": null,
  "errors": 0,
  "warnings": 0,
  "networkFailures": 0,
  "durationMs": 5000,
  "pageState": {
    "title": "Portfolio AI Platform",
    "hasContent": true,
    "tables": 1,
    "charts": 0,
    "errorElements": 0,
    "loadingElements": 0
  },
  "console": {
    "errorCount": 0,
    "warningCount": 0,
    "errors": [],
    "warnings": []
  },
  "network": {
    "failureCount": 0,
    "failures": []
  }
}
```

---

## Analyzing Results

### Find errors across all captures

```bash
find solution_state/*/pages -name "*.json" -exec jq -r '
  select(.console.errorCount > 0) |
  "\(.pageName): \(.console.errorCount) errors"
' {} \;
```

### Find network failures

```bash
find solution_state/* -name "*.json" -exec jq -r '
  select(.network.failureCount > 0) |
  "\(.pageName): \(.network.failureCount) network failures"
' {} \;
```

### Compare two captures

```bash
BASELINE="solution_state/20251210-215527"
CURRENT="solution_state/$(ls -t solution_state | head -1)"

for json in "$CURRENT"/pages/*.json; do
  page=$(basename "$json")
  curr=$(jq '.console.errorCount' "$json")
  base=$(jq '.console.errorCount' "$BASELINE/pages/$page" 2>/dev/null || echo "0")
  if [ "$curr" -gt "$base" ]; then
    echo "REGRESSION: $page - errors $base -> $curr"
  fi
done
```

---

## Success Criteria

A capture passes when:
- [ ] All pages load without console errors
- [ ] All tabs navigate correctly
- [ ] Expanded sections render content
- [ ] Mobile views are usable
- [ ] Charts render (canvas/svg present)
- [ ] Tables populated (row count > 0)
- [ ] No network failures (4xx/5xx)

---

## Retention Policy

- Keep baseline captures for comparison
- Archive old captures monthly
- Delete captures older than 30 days (unless marked as baseline)

---

## Recent Captures

| Date | Status | Notes |
|------|--------|-------|
| 2025-12-10 21:55 | PASS | Initial baseline, 0 errors |

---

**Version**: 1.0.0 | **Updated**: 2025-12-10
