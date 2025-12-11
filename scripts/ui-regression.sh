#!/bin/bash
# Full UI Regression Capture Script
# Usage: bash ~/portfolio-ai/scripts/ui-regression.sh [--quick|--pages|--tabs|--expanded|--mobile|--full]
#
# Captures screenshots + JSON reports for all pages, tabs, expanded sections, and mobile views.
# Output: ~/portfolio-ai/solution_state/{timestamp}/

set -e

BASE_URL="http://192.168.8.233:3000"
OUT="$HOME/portfolio-ai/solution_state/$(date +%Y%m%d-%H%M%S)"
S="$HOME/portfolio-ai/.claude/skills/browser-automation/scripts"
REGRESSION="node $S/regression-check.js"
EMULATE="node $S/emulate.js"

# Parse arguments
MODE="${1:-full}"

echo "UI Regression Capture - Mode: $MODE"
echo "Output: $OUT"
echo ""

mkdir -p "$OUT"/{pages,tabs,expanded,mobile}

# ============================================
# PAGES (9 pages)
# ============================================
capture_pages() {
  echo "=== Capturing All Pages ==="
  $REGRESSION "$BASE_URL/" "$OUT/pages" --wait-ms 8000
  $REGRESSION "$BASE_URL/watchlist" "$OUT/pages" --wait-ms 5000
  $REGRESSION "$BASE_URL/portfolio" "$OUT/pages" --wait-ms 3000
  $REGRESSION "$BASE_URL/trading" "$OUT/pages" --wait-ms 3000
  $REGRESSION "$BASE_URL/backtest" "$OUT/pages" --wait-ms 3000
  $REGRESSION "$BASE_URL/agents" "$OUT/pages" --wait-ms 3000
  $REGRESSION "$BASE_URL/status" "$OUT/pages" --wait-ms 5000
  $REGRESSION "$BASE_URL/capabilities" "$OUT/pages" --wait-ms 3000
  $REGRESSION "$BASE_URL/settings" "$OUT/pages" --wait-ms 2000
}

# ============================================
# TABS (actual tab names from UI)
# ============================================
capture_tabs() {
  echo "=== Capturing All Tabs ==="

  # Capabilities tabs (10 tabs)
  for t in Dashboard Vision Features Workflows Sources Rules DB Log Tasks API; do
    $REGRESSION "$BASE_URL/capabilities" "$OUT/tabs" --click-tab "$t" --wait-ms 2000
  done

  # Trading tabs (2)
  $REGRESSION "$BASE_URL/trading" "$OUT/tabs" --click-tab "Open Positions" --wait-ms 2000
  $REGRESSION "$BASE_URL/trading" "$OUT/tabs" --click-tab "Closed Trades" --wait-ms 2000
}

# ============================================
# EXPANDED SECTIONS (dynamic based on data)
# ============================================
capture_expanded() {
  echo "=== Capturing Expanded Sections ==="

  # Watchlist expanded rows (first 3 tickers)
  TICKERS=$(curl -s "http://localhost:8000/api/watchlist" | jq -r '.items[:3][].symbol // empty' 2>/dev/null || echo "")
  if [ -n "$TICKERS" ]; then
    for T in $TICKERS; do
      $REGRESSION "$BASE_URL/watchlist" "$OUT/expanded" --expand-row "$T" --wait-ms 3000
    done
  else
    echo "Warning: No watchlist tickers found, skipping expanded captures"
  fi
}

# ============================================
# MOBILE VIEWPORTS (7 pages)
# ============================================
capture_mobile() {
  echo "=== Capturing Mobile Views ==="

  $EMULATE device "$BASE_URL/" "iPhone 12 Pro" "$OUT/mobile/dashboard.png"
  $EMULATE device "$BASE_URL/watchlist" "iPhone 12 Pro" "$OUT/mobile/watchlist.png"
  $EMULATE device "$BASE_URL/portfolio" "iPhone 12 Pro" "$OUT/mobile/portfolio.png"
  $EMULATE device "$BASE_URL/trading" "iPhone 12 Pro" "$OUT/mobile/trading.png"
  $EMULATE device "$BASE_URL/capabilities" "iPhone 12 Pro" "$OUT/mobile/capabilities.png"
  $EMULATE device "$BASE_URL/status" "iPhone 12 Pro" "$OUT/mobile/status.png"
  $EMULATE device "$BASE_URL/settings" "iPhone 12 Pro" "$OUT/mobile/settings.png"
}

# ============================================
# QUICK MODE (Dashboard + Watchlist only)
# ============================================
capture_quick() {
  echo "=== Quick Capture (Dashboard + Watchlist) ==="
  $REGRESSION "$BASE_URL/" "$OUT/pages" --wait-ms 8000
  $REGRESSION "$BASE_URL/watchlist" "$OUT/pages" --wait-ms 5000

  # First watchlist ticker expanded
  T=$(curl -s "http://localhost:8000/api/watchlist" | jq -r '.items[0].symbol // empty' 2>/dev/null || echo "")
  if [ -n "$T" ]; then
    $REGRESSION "$BASE_URL/watchlist" "$OUT/expanded" --expand-row "$T" --wait-ms 3000
  fi
}

# ============================================
# EXECUTE BASED ON MODE
# ============================================
case "$MODE" in
  --quick|-q)
    capture_quick
    ;;
  --pages|-p)
    capture_pages
    ;;
  --tabs|-t)
    capture_tabs
    ;;
  --expanded|-e)
    capture_expanded
    ;;
  --mobile|-m)
    capture_mobile
    ;;
  --full|-f|full|*)
    capture_pages
    capture_tabs
    capture_expanded
    capture_mobile
    ;;
esac

# ============================================
# GENERATE REPORT
# ============================================
echo ""
echo "=== Generating Report ==="

SCREENSHOTS=$(find "$OUT" -name "*.png" 2>/dev/null | wc -l)
REPORTS=$(find "$OUT" -name "*.json" 2>/dev/null | wc -l)
ERRORS=$(find "$OUT" -name "*.json" -exec cat {} \; 2>/dev/null | jq -s '[.[].console.errorCount // 0] | add' 2>/dev/null || echo "0")
WARNINGS=$(find "$OUT" -name "*.json" -exec cat {} \; 2>/dev/null | jq -s '[.[].console.warningCount // 0] | add' 2>/dev/null || echo "0")

# Determine status
if [ "$ERRORS" = "0" ] || [ "$ERRORS" = "null" ]; then
  STATUS="PASS"
else
  STATUS="FAIL"
fi

# Generate REPORT.md
cat > "$OUT/REPORT.md" << EOF
# UI Regression Report

**Date**: $(date '+%Y-%m-%d %H:%M:%S')
**Command**: \`/test_it\` or \`bash scripts/ui-regression.sh $MODE\`
**Status**: $STATUS

---

## Summary

| Metric | Value |
|--------|-------|
| Screenshots | $SCREENSHOTS |
| JSON Reports | $REPORTS |
| Console Errors | $ERRORS |
| Console Warnings | $WARNINGS |

---

## Coverage

| Category | Count |
|----------|-------|
| Pages | $(ls "$OUT/pages"/*.png 2>/dev/null | wc -l)/9 |
| Tabs | $(ls "$OUT/tabs"/*.png 2>/dev/null | wc -l)/12 |
| Expanded | $(ls "$OUT/expanded"/*.png 2>/dev/null | wc -l) |
| Mobile | $(ls "$OUT/mobile"/*.png 2>/dev/null | wc -l)/7 |

---

## Result

$([ "$STATUS" = "PASS" ] && echo "All tests pass. No regressions detected." || echo "ERRORS DETECTED - Review JSON reports for details.")
EOF

# ============================================
# SUMMARY
# ============================================
echo ""
echo "=== Capture Complete ==="
echo "Screenshots: $SCREENSHOTS"
echo "Reports: $REPORTS"
echo "Console Errors: $ERRORS"
echo "Console Warnings: $WARNINGS"
echo "Status: $STATUS"
echo ""
echo "Output directory: $OUT"
echo "Report: $OUT/REPORT.md"

# List any pages with errors
if [ "$STATUS" = "FAIL" ]; then
  echo ""
  echo "Pages with errors:"
  find "$OUT" -name "*.json" -exec sh -c 'cat "$1" | jq -r "select(.console.errorCount > 0) | \"\(.pageName): \(.console.errorCount) errors\""' _ {} \; 2>/dev/null
fi

exit 0
