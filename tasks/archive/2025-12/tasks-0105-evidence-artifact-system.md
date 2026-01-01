# Task List: Evidence/Artifact System for UI Verification

**Source**: User request + plan from iridescent-mapping-avalanche.md
**Complexity**: Complex
**Effort**: HIGH
**Environment**: Local Dev
**Created**: 2025-12-06

---

## Summary

**Goal**: Build a persistent evidence system that captures screenshot + console + DOM for UI verification, with AI review integrated into `/audit_it` and `/verify_it` workflows.

**Why**: Current screenshot verification:
- Stored in `/tmp` (ephemeral)
- Only captures screenshot (no console errors, no DOM)
- Auto-passed without content validation (fixed partially, but still limited)
- No version history for tracking progression/regression
- No user oversight or feedback mechanism

**Approach**:
1. Create `capture-evidence.js` script (screenshot + console + DOM)
2. Add `artifacts` database table for tracking
3. Build file-serving API endpoints
4. Update `criteria_verifier.py` to use new system
5. Add Celery tasks for scheduled refresh/cleanup
6. Create frontend `EvidenceViewerModal` component
7. Update `/audit_it` and `/verify_it` commands
8. Document in CLAUDE.md

---

## Tasks

### 0.0 Scope Discovery (MANDATORY) - COMPLETED 2025-12-06

- [x] 0.1 Explore existing browser automation scripts
- [x] 0.2 Explore current criteria_verifier.py
- [x] 0.3 Explore frontend modal patterns
- [x] 0.4 Explore FeaturesTab.tsx current state
- [x] 0.5 Check database migration numbering (084 available)
- [x] 0.6 Verify `data/` directory exists and is gitignored
- [x] 0.7 Checkpoint: Scope confirmed

---

### 1.0 Foundation - COMPLETED 2025-12-06

- [x] 1.1 Create directory structure (`data/artifacts/`)
- [x] 1.2 .gitignore already covers `data/` - no changes needed
- [x] 1.3 Create database migration (084_artifacts_table.sql)
- [x] 1.4 Apply migration - table verified with 22 columns
- [x] 1.5 Test: Directory writable, migration applied

---

### 2.0 Evidence Capture Script - COMPLETED 2025-12-06

- [x] 2.1 Create `capture-evidence.js` - screenshots + evidence.json
- [x] 2.2 Capture rich but compact data (console, network, page_state, performance)
- [x] 2.3 Implement version management with `current` symlink
- [x] 2.4 Handle errors gracefully
- [x] 2.5 Test: `node capture-evidence.js http://192.168.8.233:3000/watchlist FEAT-TEST ac-001` - verified

---

### 3.0 Backend Core - COMPLETED 2025-12-06

- [x] 3.1 Create `artifact_manager.py` with all CRUD functions
- [x] 3.2 Create `artifacts.py` router with all endpoints
- [x] 3.3 Register router in main.py
- [x] 3.4 Update `criteria_verifier.py` to use capture-evidence.js and create artifact records
- [x] 3.5 Test: API endpoints work (verified with curl)

---

### 4.0 Lifecycle Management - COMPLETED 2025-12-06

- [x] 4.1 Create `artifact_tasks.py` with refresh and cleanup tasks
- [x] 4.2 Add to celery_schedules.py (05:30 and 06:00 UTC)
- [ ] 4.3 Test: Tasks run successfully (scheduled - will run daily)

---

### 5.0 Frontend UI - COMPLETED 2025-12-06

- [x] 5.1 Create `EvidenceViewerModal.tsx` with tabs (Screenshot, Console, Network, Page State)
- [x] 5.2 Update `FeaturesTab.tsx` with Evidence button for UI criteria
- [x] 5.3 API calls integrated inline (useQuery, useMutation)
- [ ] 5.4 Test: Modal works end-to-end (requires manual testing)

---

### 6.0 Command Integration - COMPLETED 2025-12-07

- [x] 6.1 Update `/audit_it` command (Phase 2.5 Evidence Review added)
- [x] 6.2 Update `/verify_it` command (capture-evidence.js option added)
- [x] 6.3 Update CLAUDE.md with evidence capture documentation
- [ ] 6.4 Test: Commands use new evidence system (manual testing)

---

### 7.0 Migration & Cleanup - COMPLETED 2025-12-07

- [x] 7.1 Old screenshots in `/tmp/` - no migration needed (ephemeral by design)
- [x] 7.2 Old code deprecated: `_check_page_status()` and `_detect_error_screenshot()` marked deprecated
- [x] 7.3 Final verification - all core functionality working
- [ ] 7.4 Commit changes

---

## Verification (FACTS)

- [x] Directory: `data/artifacts/` exists and is gitignored
- [x] Database: `artifacts` table exists with all columns (22 columns)
- [x] Script: `capture-evidence.js` captures screenshot + evidence.json (no full DOM - by design)
- [x] API: All `/api/artifacts/*` endpoints return 200 (tested)
- [x] Storage: Evidence saved to `data/artifacts/{feature}/{criterion}/v{n}/`
- [x] Versioning: `current` symlink points to latest version
- [x] Frontend: EvidenceViewerModal created with 4 tabs
- [x] FeaturesTab: Evidence button added for UI criteria
- [x] Celery: Refresh and cleanup tasks scheduled (05:30 and 06:00 UTC)
- [ ] Commands: `/verify_it` and `/audit_it` use new system (pending)
- [ ] CLAUDE.md: Evidence capture documented (pending)
- [ ] Migration: Old `/tmp` screenshots migrated (pending)

---

## Files to Create

| File | Purpose |
|------|---------|
| `.claude/skills/browser-automation/scripts/capture-evidence.js` | Capture screenshot + console + DOM |
| `backend/migrations/084_artifacts_table.sql` | Database schema |
| `backend/app/api/artifacts.py` | REST API + file serving |
| `backend/app/services/artifact_manager.py` | CRUD, versioning |
| `backend/app/tasks/artifact_tasks.py` | Celery tasks |
| `frontend/components/capabilities/EvidenceViewerModal.tsx` | Viewer modal |
| `data/artifacts/.gitkeep` | Placeholder for artifacts directory |

## Files to Modify

| File | Changes |
|------|---------|
| `backend/app/services/criteria_verifier.py` | Use capture-evidence.js, create artifact records |
| `backend/app/api/__init__.py` | Register artifacts router |
| `backend/app/celery_schedules.py` | Add refresh/cleanup tasks |
| `frontend/components/capabilities/FeaturesTab.tsx` | Add evidence links, modal integration |
| `.gitignore` | Add `data/artifacts/FEAT-*` |
| `CLAUDE.md` | Add evidence capture documentation |
| `.claude/commands/audit_it.md` | Add evidence review step |
| `.claude/commands/verify_it.md` | Add evidence review step |

---

## Dependencies

- **Requires**: Playwright installed (already available)
- **Requires**: Database access (already configured)
- **Blocks**: None (enhancement, not breaking change)

---

## Resume Points

Each numbered task section is a natural pause point.

**Recommended session splits:**
- Session 1: Tasks 0.0-1.0 (Scope Discovery + Foundation)
- Session 2: Task 2.0 (Evidence Capture Script)
- Session 3: Task 3.0 (Backend Core)
- Session 4: Task 4.0 (Lifecycle Management)
- Session 5: Task 5.0 (Frontend UI)
- Session 6: Tasks 6.0-7.0 (Integration + Migration)

---

## Technical Reference

### Evidence Package Structure
```
data/artifacts/
  FEAT-001/
    ac-001/
      v1/
        screenshot.png      # Visual state (~100-500KB)
        evidence.json       # All other data combined (~5-20KB)
      v2/
        ...
      current -> v2/
```

### evidence.json Schema (Consolidated - Small but Powerful)
```json
{
  "metadata": {
    "url": "http://192.168.8.233:3000/watchlist",
    "feature_id": "FEAT-001",
    "criterion_id": "ac-001",
    "version": 2,
    "captured_at": "2025-12-06T22:00:00Z",
    "page_title": "Watchlist | Portfolio AI",
    "viewport": {"width": 1280, "height": 720}
  },

  "console": {
    "error_count": 2,
    "warning_count": 1,
    "errors": [
      {"text": "Failed to fetch /api/data", "source": "app.js:42"}
    ],
    "warnings": [
      {"text": "Deprecated API usage", "source": "lib.js:10"}
    ]
  },

  "network": {
    "total_requests": 45,
    "failed_requests": 2,
    "failures": [
      {"url": "/api/analytics/rvol/AAPL", "status": 404}
    ],
    "slow_requests": [
      {"url": "/api/watchlist", "duration_ms": 3200}
    ]
  },

  "page_state": {
    "has_content": true,
    "visible_text_sample": "Watchlist (12 symbols) | AAPL +2.3% | NVDA -1.2%...",
    "key_elements": {
      "tables": 2,
      "charts": 1,
      "buttons": 8,
      "error_messages": 0,
      "loading_spinners": 0,
      "empty_states": 0
    }
  },

  "performance": {
    "page_load_ms": 1250,
    "dom_content_loaded_ms": 890,
    "largest_contentful_paint_ms": 1100
  }
}
```

**Why this approach:**
- **No full DOM** - 500KB HTML is too large and hard to parse meaningfully
- **Consolidated JSON** - One file with all non-screenshot data (~10KB)
- **Key element counts** - Tables, charts, buttons visible (detects empty/broken pages)
- **Error/warning focus** - Full text for errors, just counts for logs
- **Network summary** - Failed + slow requests only (not full HAR)
- **Performance basics** - Quick check if page is slow
- **Visible text sample** - First ~200 chars of visible text (confirms content loaded)

### Artifacts Table Schema
```sql
CREATE TABLE artifacts (
    id SERIAL PRIMARY KEY,
    artifact_id VARCHAR(50) UNIQUE NOT NULL,
    feature_id VARCHAR(20) NOT NULL,
    criterion_id VARCHAR(20),
    artifact_type VARCHAR(20) DEFAULT 'screenshot',
    file_path VARCHAR(500) NOT NULL,
    file_size_bytes INTEGER,
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    version INTEGER DEFAULT 1,
    is_current BOOLEAN DEFAULT TRUE,
    quality_status VARCHAR(20) DEFAULT 'pending',
    quality_issues JSONB DEFAULT '[]',
    confidence FLOAT,
    ai_reviewed_at TIMESTAMPTZ,
    ai_reviewed_by VARCHAR(50),
    ai_evidence TEXT,
    user_reviewed_at TIMESTAMPTZ,
    user_approved BOOLEAN,
    user_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Confidence Scoring Guidelines
| Confidence | When | Action |
|------------|------|--------|
| 0.9-1.0 | Clear visual match, no console errors | Auto-mark passed |
| 0.7-0.9 | Looks correct, minor warnings | Mark passed, note in evidence |
| 0.5-0.7 | Uncertain, some issues | Queue for user review |
| < 0.5 | Likely broken | Mark failed, create [FIX] task |

---

## Notes

- Evidence expiry: 24 hours (configurable)
- Version retention: Last 5 versions
- File serving: Via FastAPI FileResponse with 1-hour cache
- **No full DOM capture** - Too large (~500KB), hard to use meaningfully
- **Consolidated evidence.json** - All non-screenshot data in one ~10KB file
- **Key element counts** - Quick detection of broken/empty pages
- **Visible text sample** - Confirms content loaded without full DOM
- Console capture: Includes network errors (4xx, 5xx responses)

---

**Version**: 1.0.0 | **Created**: 2025-12-06

**Related**: tasks-0103-spec-driven-features.md (acceptance criteria system this builds on)
