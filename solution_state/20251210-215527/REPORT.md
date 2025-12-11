# UI Regression Report

**Date**: 2025-12-10 21:55:27
**Command**: `/test_it`
**Status**: PASS

---

## Coverage Summary

| Category | Captured | Expected | Status |
|----------|----------|----------|--------|
| Pages | 9 | 9 | PASS |
| Tabs | 12 | 12 | PASS |
| Expanded | 3 | 3+ | PASS |
| Mobile | 7 | 7 | PASS |
| **Total** | **31** | ~31 | **PASS** |

---

## Error Analysis

| Metric | Count | Status |
|--------|-------|--------|
| Console Errors | 0 | PASS |
| Console Warnings | 10 | INFO |
| Network Failures | 0 | PASS |

### Warnings Detail

| Page | Warnings | Notes |
|------|----------|-------|
| index (Dashboard) | 6 | React hydration / chart library |
| agents | 4 | Chart library deprecation notices |

---

## Page State Summary

| Page | Tables | Charts | Loading | Status |
|------|--------|--------|---------|--------|
| index | 0 | 3 | 5 | OK |
| watchlist | 1 | 0 | 0 | OK |
| portfolio | 0 | 0 | 0 | OK |
| trading | 1 | 0 | 0 | OK |
| backtest | 0 | 0 | 0 | OK |
| agents | 1 | 2 | 0 | OK |
| status | 0 | 0 | 2 | OK |
| capabilities | 0 | 0 | 0 | OK |
| settings | 0 | 0 | 0 | OK |

---

## Files Generated

```
20251210-215527/
├── pages/           # 9 pages (18 files: png + json)
│   ├── index.png
│   ├── index.json
│   ├── watchlist.png
│   ├── watchlist.json
│   ├── portfolio.png
│   ├── portfolio.json
│   ├── trading.png
│   ├── trading.json
│   ├── backtest.png
│   ├── backtest.json
│   ├── agents.png
│   ├── agents.json
│   ├── status.png
│   ├── status.json
│   ├── capabilities.png
│   ├── capabilities.json
│   ├── settings.png
│   └── settings.json
├── tabs/            # 12 tabs (24 files: png + json)
│   ├── capabilities-tab-*.png/json (10 tabs)
│   └── trading-tab-*.png/json (2 tabs)
├── expanded/        # 3 expanded rows (6 files: png + json)
│   ├── watchlist-expanded-iren.png/json
│   ├── watchlist-expanded-amba.png/json
│   └── watchlist-expanded-apld.png/json
├── mobile/          # 7 mobile views (7 files: png only)
│   ├── dashboard.png
│   ├── watchlist.png
│   ├── portfolio.png
│   ├── trading.png
│   ├── capabilities.png
│   ├── status.png
│   └── settings.png
└── REPORT.md        # This file
```

---

## Success Criteria

- [x] All 9 pages load without console errors
- [x] All 12 tabs navigate correctly
- [x] Expanded sections show expected content
- [x] Mobile views captured (7 pages)
- [x] Charts render (canvas/svg elements present)
- [x] Tables populated where expected
- [x] No network failures (4xx/5xx)
- [x] JSON reports show 0 errors

---

## Notes

- All tests executed in dark mode
- Network IP used: 192.168.8.233:3000
- Browser: Chromium (Playwright)
- Viewport: 1280x720 (desktop), iPhone 12 Pro (mobile)

---

**Result**: All tests pass. No regressions detected.
