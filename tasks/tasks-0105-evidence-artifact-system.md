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

### 0.0 Scope Discovery (MANDATORY)

- [ ] 0.1 Explore existing browser automation scripts
  - What scripts exist in `.claude/skills/browser-automation/scripts/`?
  - How do `screenshot.js` and `console.js` work?
  - What's the pattern for new scripts?

- [ ] 0.2 Explore current criteria_verifier.py
  - How does `_verify_ui_criterion` currently work?
  - Where does it save screenshots?
  - How is the result stored in the database?

- [ ] 0.3 Explore frontend modal patterns
  - What modals exist in `frontend/components/`?
  - How is the Dialog component used?
  - What's the pattern for image display?

- [ ] 0.4 Explore FeaturesTab.tsx current state
  - How are acceptance criteria rendered?
  - Where would evidence links be added?
  - How is the expanded row structured?

- [ ] 0.5 Check database migration numbering
  - What's the latest migration number?
  - Confirm 084 is available

- [ ] 0.6 Verify `data/` directory exists and is gitignored
  - Check if `data/` exists in project root
  - Check `.gitignore` for data patterns

- [ ] 0.7 Checkpoint: Confirm scope before proceeding
  - List all files to create
  - List all files to modify
  - Confirm no conflicts

**SCOPE MUST BE CONFIRMED BEFORE PROCEEDING**

---

### 1.0 Foundation

- [ ] 1.1 Create directory structure
  ```
  mkdir -p ~/portfolio-ai/data/artifacts
  touch ~/portfolio-ai/data/artifacts/.gitkeep
  ```

- [ ] 1.2 Update .gitignore
  - Add: `data/artifacts/FEAT-*` (ignore evidence files, keep .gitkeep)

- [ ] 1.3 Create database migration
  - File: `backend/migrations/084_artifacts_table.sql`
  - Table: `artifacts` with all columns from plan
  - Indexes for: feature_id, expires_at, quality_status, user_notes

- [ ] 1.4 Apply migration
  - Run migration via Python or psql
  - Verify table exists with `\d artifacts`

- [ ] 1.5 Test: Directory writable, migration applied

---

### 2.0 Evidence Capture Script

- [ ] 2.1 Create `capture-evidence.js`
  - File: `.claude/skills/browser-automation/scripts/capture-evidence.js`
  - Usage: `node capture-evidence.js <url> <feature-id> <criterion-id>`
  - Outputs (2 files only):
    - `screenshot.png` - Full page screenshot
    - `evidence.json` - Consolidated: metadata, console, network, page_state, performance

- [ ] 2.2 Capture rich but compact data
  - **Console**: Error/warning count + full text for errors only
  - **Network**: Failed requests (4xx/5xx) + slow requests (>3s)
  - **Page state**: Key element counts (tables, charts, buttons, errors, spinners, empty states)
  - **Performance**: Page load time, LCP
  - **Text sample**: First ~200 chars of visible text (confirms content)

- [ ] 2.3 Implement version management
  - Detect existing versions in `data/artifacts/{feature}/{criterion}/`
  - Create `v{n+1}/` directory
  - Update `current` symlink

- [ ] 2.4 Handle errors gracefully
  - Page load timeout → still capture what we can
  - Navigation error → record in evidence.json
  - Return JSON result with success/failure

- [ ] 2.5 Test: Capture evidence for single page
  ```
  node capture-evidence.js http://192.168.8.233:3000/watchlist FEAT-TEST ac-001
  ```
  - Verify 2 files created (screenshot.png, evidence.json)
  - Verify evidence.json < 20KB
  - Verify symlink works
  - Verify console errors captured (if any)

---

### 3.0 Backend Core

- [ ] 3.1 Create `artifact_manager.py`
  - File: `backend/app/services/artifact_manager.py`
  - Functions:
    - `save_artifact()` - Create DB record after capture
    - `get_artifact()` - Get current artifact for feature/criterion
    - `get_artifact_versions()` - Get all versions
    - `get_pending_review()` - Get artifacts needing AI review
    - `get_with_user_notes()` - Get artifacts with user feedback
    - `update_ai_review()` - Record AI review result
    - `update_user_review()` - Record user approval/notes
    - `cleanup_old_versions()` - Delete beyond retention limit

- [ ] 3.2 Create `artifacts.py` router
  - File: `backend/app/api/artifacts.py`
  - Endpoints:
    - `GET /api/artifacts/screenshots/{path:path}` - Serve files
    - `GET /api/artifacts/{feature_id}/{criterion_id}` - Get metadata + versions
    - `GET /api/artifacts/needs-review` - List pending AI review
    - `GET /api/artifacts/with-notes` - List with user notes
    - `POST /api/artifacts/refresh` - Trigger capture (single/batch/all)
    - `POST /api/artifacts/{artifact_id}/review` - Submit user review
    - `GET /api/artifacts/summary` - Stats

- [ ] 3.3 Register router in main.py
  - Import and include artifacts router

- [ ] 3.4 Update `criteria_verifier.py`
  - Modify `_verify_ui_criterion()`:
    - Use `capture-evidence.js` instead of `screenshot.js`
    - Create artifact record in database
    - Return artifact reference in `verification_output`
  - Remove: `_check_page_status()` (now handled by capture script)
  - Remove: `_detect_error_screenshot()` (file size heuristic - bad)

- [ ] 3.5 Test: API endpoints work
  - `curl http://localhost:8000/api/artifacts/summary`
  - `curl http://localhost:8000/api/artifacts/FEAT-001/ac-001`

---

### 4.0 Lifecycle Management

- [ ] 4.1 Create `artifact_tasks.py`
  - File: `backend/app/tasks/artifact_tasks.py`
  - Tasks:
    - `refresh_expired_artifacts` - Refresh where `expires_at < NOW()`
    - `cleanup_old_versions` - Delete versions > retention limit
    - `capture_all_evidence` - Batch capture for all UI criteria

- [ ] 4.2 Add to celery_schedules.py
  - `refresh-expired-artifacts`: Daily 05:30 UTC
  - `cleanup-old-versions`: Daily 06:00 UTC

- [ ] 4.3 Test: Tasks run successfully
  - Trigger manually via API or Celery
  - Verify expired artifacts refreshed
  - Verify old versions cleaned up

---

### 5.0 Frontend UI

- [ ] 5.1 Create `EvidenceViewerModal.tsx`
  - File: `frontend/components/capabilities/EvidenceViewerModal.tsx`
  - Features:
    - Tabs: Screenshot | Console | DOM
    - Screenshot: Full-size image display
    - Console: Formatted JSON with error highlighting
    - DOM: Scrollable HTML view (or collapsible tree)
    - Version navigation (prev/next)
    - User review: Approve/Reject buttons
    - User notes: Text input field
    - Refresh button: Trigger new capture

- [ ] 5.2 Update `FeaturesTab.tsx`
  - Add evidence link in criteria display
  - Show confidence badge if available
  - Show "Needs Review" badge for low confidence
  - Wire up modal open/close

- [ ] 5.3 Add API client functions
  - `fetchEvidenceMetadata(featureId, criterionId)`
  - `submitUserReview(artifactId, approved, notes)`
  - `refreshEvidence(featureId, criterionId)`

- [ ] 5.4 Test: Modal works end-to-end
  - Click evidence link → modal opens
  - Tabs switch correctly
  - Version navigation works
  - User review submits

---

### 6.0 Command Integration

- [ ] 6.1 Update `/audit_it` command
  - Add step: "Review pending evidence" after feature verification
  - Query: `GET /api/artifacts/needs-review`
  - For each: Read screenshot + console + DOM, assign confidence
  - Query: `GET /api/artifacts/with-notes`
  - For each: Read user notes, take action

- [ ] 6.2 Update `/verify_it` command
  - Add step: Review evidence for specific feature
  - Trigger evidence capture if stale (>24h)
  - Review and assign confidence

- [ ] 6.3 Update CLAUDE.md
  - Add section: "Evidence Capture for UI Verification"
  - Document: capture-evidence.js usage
  - Document: When to capture (development, verification)
  - Document: How to review (what to look for)

- [ ] 6.4 Test: Commands use new evidence system
  - Run `/verify_it FEAT-001` → evidence captured and reviewed
  - Run `/audit_it --target` → evidence reviewed

---

### 7.0 Migration & Cleanup

- [ ] 7.1 Migrate existing screenshots
  - Script to move `/tmp/criteria-screenshots/*.png` to new structure
  - Create artifact records for migrated files
  - Set version = 1, expires_at = NOW() + 24h

- [ ] 7.2 Remove old screenshot code
  - Delete or deprecate `_detect_error_screenshot()`
  - Update any references to `/tmp/criteria-screenshots/`

- [ ] 7.3 Final verification
  - All UI criteria have evidence captured
  - Evidence viewable in UI
  - Commands work with new system
  - No references to old /tmp path

- [ ] 7.4 Commit changes

---

## Verification (FACTS)

- [ ] Directory: `data/artifacts/` exists and is gitignored
- [ ] Database: `artifacts` table exists with all columns
- [ ] Script: `capture-evidence.js` captures screenshot + console + DOM
- [ ] API: All `/api/artifacts/*` endpoints return 200
- [ ] Storage: Evidence saved to `data/artifacts/{feature}/{criterion}/v{n}/`
- [ ] Versioning: `current` symlink points to latest version
- [ ] Frontend: EvidenceViewerModal renders all tabs
- [ ] FeaturesTab: Evidence links visible in criteria section
- [ ] Commands: `/verify_it` and `/audit_it` use new system
- [ ] CLAUDE.md: Evidence capture documented
- [ ] Celery: Refresh and cleanup tasks scheduled
- [ ] Migration: Old `/tmp` screenshots migrated

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
