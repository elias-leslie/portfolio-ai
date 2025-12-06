# Task List: Acceptance Criteria Auto-Verification System

**Source**: Continuation of tasks-0104 (Backfill Acceptance Criteria)
**Complexity**: High
**Effort**: HIGH
**Environment**: Local Dev
**Created**: 2025-12-06

---

## Summary

**Goal**: Make acceptance criteria actually useful by enabling auto-verification and tracking.

**Current state** (verified 2025-12-06):
- 165 features with 332 acceptance criteria total
- ALL 332 criteria have `passed: null` (0% verified)
- Existing schema: id, criterion, verification, type, passed
- Missing fields: verified_at, verified_by, verification_output
- Vision goals stored as TEXT[] array (no lookup table)
- /verify_it already has Step 8.5 for manual criteria verification
- No scheduled auto-verification exists

**Target state**:
- Auto-verify API-type criteria (curl commands) via scheduled task
- Auto-verify test-type criteria (pytest) via scheduled task
- Auto-verify UI-type criteria (screenshots) via browser automation
- Manual toggle for criteria that can't be auto-verified
- Full verification tracking (timestamp, method, output)
- Aggregate stats visible in UI ("142/328 passing")
- Vision goals normalized to lookup table
- **API-first design**: Claude Code can access all verification data via simple curl commands
- **Slash commands updated**: /audit_it, /verify_it, /check_it leverage verification data

---

## Phase 0: Scope Discovery ✅ COMPLETE

**Completed**: 2025-12-06

### Findings Summary

**Schema State**:
- AcceptanceCriterion model exists in `features_router.py:106-113`
- Fields: id, criterion, verification, type, passed (all present)
- Missing: verified_at, verified_by, verification_output
- JSONB column in feature_capabilities table with GIN index

**Subprocess Patterns Found** (reusable for auto-verification):
- `git_automation.py` - subprocess.run with timeout, error handling
- `claude_client.py`, `gemini_client.py` - 5-min timeout, JSON output parsing
- `maintenance/utils.py` - asyncio.create_subprocess_exec pattern
- Safety: All use list args (no shell=True), explicit timeouts, proper cleanup

**Browser Automation**:
- 14 Playwright scripts in `.claude/skills/browser-automation/scripts/`
- Key scripts: screenshot.js, console.js, interact.js, execute.js
- All use headless mode, 30s timeout, proper cleanup

**Database State**:
- No vision_goals lookup table exists
- No criteria_verification_runs table exists
- No verification scheduled tasks in celery_schedules.py

**Slash Commands**:
- /verify_it v3.0.0 already has Step 8.5 for criteria verification (manual)
- /audit_it, /do_it delegate to /verify_it (no duplication needed)
- /check_it is status-only, /task_it handles creation

**SCOPE CONFIRMED**: [x] User approved 2025-12-06

---

## Phase 1: Schema & Backend Foundation

### 1.0 Extend Acceptance Criteria Schema

- [ ] 1.1 Add verification tracking fields to JSONB structure
  ```python
  # New AcceptanceCriterion structure:
  {
    "id": "ac-001",
    "criterion": "API returns 200 with data",
    "verification": "curl -s http://localhost:8000/api/health",
    "type": "api",  # api|ui|test|backend|quality|db
    "passed": true,  # null=unverified, true=pass, false=fail
    "verified_at": "2025-12-06T10:30:00Z",  # NEW
    "verified_by": "auto",  # NEW: auto|manual|pytest|browser
    "verification_output": "..."  # NEW: actual output (truncated)
  }
  ```

- [ ] 1.2 Create migration to update existing criteria
  ```sql
  -- Add default values for new fields in existing criteria
  UPDATE feature_capabilities
  SET acceptance_criteria = (
    SELECT jsonb_agg(
      c || jsonb_build_object(
        'verified_at', null,
        'verified_by', null,
        'verification_output', null
      )
    )
    FROM jsonb_array_elements(acceptance_criteria) c
  )
  WHERE acceptance_criteria IS NOT NULL;
  ```

- [ ] 1.3 Update Pydantic models in features_router.py
  ```python
  class AcceptanceCriterion(BaseModel):
      id: str
      criterion: str
      verification: str
      type: str  # api|ui|test|backend|quality|db
      passed: bool | None = None
      verified_at: datetime | None = None
      verified_by: str | None = None  # auto|manual|pytest|browser
      verification_output: str | None = None
  ```

### 1.1 Create Vision Goals Lookup Table

- [ ] 1.4 Create vision_goals reference table
  ```sql
  CREATE TABLE vision_goals (
    code TEXT PRIMARY KEY,  -- VG-INTEL, VG-AUTO, etc.
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,  -- intelligence, automation, portfolio, validation, reliability, ux, quality
    created_at TIMESTAMPTZ DEFAULT NOW()
  );
  ```

- [ ] 1.5 Populate vision_goals from VISION.md
  ```sql
  INSERT INTO vision_goals (code, name, description, category) VALUES
  ('VG-INTEL', 'Market Intelligence', 'AI-driven market insights and analysis', 'intelligence'),
  ('VG-AUTO', 'Autonomous Operation', 'Self-running trading and research agents', 'automation'),
  ('VG-PORT', 'Portfolio Management', 'Position tracking, analytics, optimization', 'portfolio'),
  ('VG-VALID', 'Strategy Validation', 'Backtesting, walk-forward, monte carlo', 'validation'),
  ('VG-RELY', 'System Reliability', 'Monitoring, health checks, data freshness', 'reliability'),
  ('VG-UX', 'User Experience', 'UI components, interactions, accessibility', 'ux'),
  ('VG-QUAL', 'Code Quality', 'Testing, documentation, standards', 'quality');
  ```

- [ ] 1.6 Create API endpoint for vision goals
  ```
  GET /api/vision-goals  → list all goals with descriptions
  GET /api/vision-goals/{code}  → single goal details
  ```

- [ ] 1.7 Update Features tab UI to show vision goal tooltips

---

## Phase 2: Auto-Verification Engine

**Goal**: Build a service that can automatically execute verification commands and record results.

### 2.0 Core Verification Service

- [ ] 2.1 Create verification service module
  ```
  backend/app/services/criteria_verifier.py
  ```
  Core class structure:
  ```python
  class CriteriaVerifier:
      """Auto-verification engine for acceptance criteria."""

      async def verify_criterion(self, feature_id: str, criterion: dict) -> dict:
          """Route to appropriate verifier based on type."""

      async def verify_feature(self, feature_id: str) -> list[dict]:
          """Verify all criteria for a feature."""

      async def verify_all_automatable(self) -> dict:
          """Verify all API/test/UI criteria across all features."""
  ```

### 2.1 API Criteria Verification (type="api")

- [ ] 2.2 Implement API criteria parser
  Parse verification commands like:
  ```
  curl -s http://localhost:8000/api/health | jq '.status'
  curl -s http://localhost:8000/api/market/fear-greed | jq '{value: .value}'
  ```
  Extract:
  - URL (must be localhost only)
  - jq filter (if present)
  - Expected output pattern (optional)

- [ ] 2.3 Implement API criteria executor
  ```python
  async def verify_api_criterion(self, criterion: dict) -> dict:
      """Execute curl command and evaluate result."""
      # 1. Parse verification string
      url, jq_filter = self._parse_curl_command(criterion["verification"])

      # 2. Execute HTTP request (not subprocess - use httpx)
      async with httpx.AsyncClient(timeout=10.0) as client:
          response = await client.get(url)

      # 3. Apply jq filter if present (use jq library or simple json path)
      output = self._apply_jq_filter(response.json(), jq_filter)

      # 4. Determine pass/fail
      passed = response.status_code == 200 and output is not None

      # 5. Return updated criterion
      return {
          **criterion,
          "passed": passed,
          "verified_at": datetime.utcnow().isoformat(),
          "verified_by": "auto",
          "verification_output": str(output)[:1000]  # Truncate
      }
  ```

- [ ] 2.4 Implement jq filter parser
  Support common patterns:
  - `.field` - extract single field
  - `.field.nested` - nested field
  - `{a: .a, b: .b}` - object projection
  - `.items | length` - array length
  - `.items[] | select(.x == y)` - filtering

- [ ] 2.5 Add safety guards for API verification
  ```python
  ALLOWED_URL_PATTERNS = [
      r"^http://localhost:\d+/api/",
      r"^http://127\.0\.0\.1:\d+/api/",
      r"^http://192\.168\.\d+\.\d+:\d+/api/",  # Local network
  ]
  MAX_TIMEOUT = 10  # seconds
  MAX_CONCURRENT = 10  # parallel requests
  ```

### 2.2 Test Criteria Verification (type="test")

- [ ] 2.6 Implement test criteria parser
  Parse verification commands like:
  ```
  pytest tests/agents/test_rules_validator.py
  pytest tests/ -k "test_watchlist"
  pytest tests/unit/test_scoring.py::test_calculate_score
  ```
  Extract:
  - Test file/path
  - Pytest args (-k, ::test_name, etc.)

- [ ] 2.7 Implement test criteria executor
  ```python
  async def verify_test_criterion(self, criterion: dict) -> dict:
      """Run pytest and check result."""
      test_cmd = self._parse_pytest_command(criterion["verification"])

      # Use asyncio.create_subprocess_exec (no shell)
      proc = await asyncio.create_subprocess_exec(
          "pytest", *test_cmd,
          cwd=BACKEND_DIR,
          stdout=asyncio.subprocess.PIPE,
          stderr=asyncio.subprocess.PIPE,
      )
      stdout, stderr = await asyncio.wait_for(
          proc.communicate(), timeout=60
      )

      passed = proc.returncode == 0
      output = stdout.decode()[-1000:]  # Last 1000 chars

      return {
          **criterion,
          "passed": passed,
          "verified_at": datetime.utcnow().isoformat(),
          "verified_by": "pytest",
          "verification_output": output
      }
  ```

- [ ] 2.8 Add safety guards for test verification
  - Only allow paths under `backend/tests/`
  - Timeout: 60 seconds max
  - No parallel test runs (could interfere)

### 2.3 UI Criteria Verification (type="ui")

- [ ] 2.9 Implement UI criteria parser
  Parse verification commands like:
  ```
  screenshot /dashboard and verify gauge visible
  screenshot /watchlist showing expanded row
  screenshot /portfolio with position cards
  ```
  Extract:
  - URL path (/dashboard, /watchlist, etc.)
  - Expected elements/text (optional)

- [ ] 2.10 Implement UI criteria executor
  ```python
  async def verify_ui_criterion(self, criterion: dict) -> dict:
      """Take screenshot using browser automation."""
      url_path, expected = self._parse_screenshot_command(criterion["verification"])

      screenshot_path = f"/tmp/criteria-screenshots/{feature_id}-{criterion['id']}.png"

      # Call Playwright script via subprocess
      proc = await asyncio.create_subprocess_exec(
          "node",
          str(BROWSER_SCRIPTS / "screenshot.js"),
          f"http://192.168.8.233:3000{url_path}",
          screenshot_path,
          stdout=asyncio.subprocess.PIPE,
          stderr=asyncio.subprocess.PIPE,
      )
      await asyncio.wait_for(proc.communicate(), timeout=30)

      # Check screenshot exists and has content
      passed = Path(screenshot_path).exists() and Path(screenshot_path).stat().st_size > 1000

      return {
          **criterion,
          "passed": passed,
          "verified_at": datetime.utcnow().isoformat(),
          "verified_by": "browser",
          "verification_output": f"Screenshot: {screenshot_path}" if passed else "Screenshot failed"
      }
  ```

- [ ] 2.11 Store screenshots with cleanup policy
  ```
  Location: /tmp/criteria-screenshots/
  Naming: FEAT-XXX-ac-001.png
  Cleanup: Keep last 5 runs per criterion (delete older)
  ```

### 2.4 Backend/Quality/DB Criteria (Manual Only)

- [ ] 2.12 Implement manual criteria handler
  ```python
  async def handle_manual_criterion(self, criterion: dict) -> dict:
      """Mark as requiring manual verification."""
      return {
          **criterion,
          "verified_by": "manual_required",
          "verification_output": f"Type '{criterion['type']}' requires manual verification"
      }
  ```
  Types requiring manual: backend, quality, db, content

- [ ] 2.13 Add "Mark as Verified" API endpoint
  ```
  PATCH /api/capabilities/features/{feature_id}/acceptance-criteria/{criterion_id}
  Body: {"passed": true, "verified_by": "manual", "evidence": "Reviewed code at X"}
  ```
  (Already exists - verify it works with new fields)

### 2.5 Result Persistence

- [ ] 2.14 Implement database update for verification results
  ```python
  async def save_verification_result(
      self, feature_id: str, criterion_id: str, result: dict
  ) -> bool:
      """Update criterion in database with verification result."""
      # Update the specific criterion in JSONB array
      # Set verified_at, verified_by, verification_output, passed
  ```

- [ ] 2.15 Add verification logging to status_log
  ```python
  # Log each verification run for audit trail
  logger.info("criterion_verified",
      feature_id=feature_id,
      criterion_id=criterion_id,
      type=criterion["type"],
      passed=result["passed"],
      duration_ms=duration
  )
  ```

---

## Phase 3: Scheduled Verification Task

### 3.0 Celery Task for Auto-Verification

- [ ] 3.1 Create scheduled task
  ```python
  @celery_app.task
  def verify_all_acceptance_criteria():
      """Run daily at 05:00 UTC after data refresh."""
      # Get all features with API/test criteria
      # Execute verifications in parallel (max 10)
      # Update database with results
      # Log summary
  ```

- [ ] 3.2 Add to beat_schedule
  ```python
  "verify_acceptance_criteria": {
      "task": "app.tasks.verify_all_acceptance_criteria",
      "schedule": crontab(hour=5, minute=0),  # 05:00 UTC
  }
  ```

- [ ] 3.3 Create verification summary table
  ```sql
  CREATE TABLE criteria_verification_runs (
    id SERIAL PRIMARY KEY,
    run_at TIMESTAMPTZ DEFAULT NOW(),
    total_criteria INT,
    api_passed INT,
    api_failed INT,
    test_passed INT,
    test_failed INT,
    ui_passed INT,
    ui_failed INT,
    manual_pending INT,
    duration_seconds FLOAT
  );
  ```

### 3.1 On-Demand Verification API

- [ ] 3.4 Add endpoint to trigger verification
  ```
  POST /api/capabilities/features/{feature_id}/verify
  → Verify all criteria for one feature

  POST /api/capabilities/verify-all
  → Queue full verification run
  ```

- [ ] 3.5 Add endpoint to verify single criterion
  ```
  POST /api/capabilities/features/{feature_id}/acceptance-criteria/{criterion_id}/verify
  → Verify one criterion and return result
  ```

---

## Phase 4: API Endpoints

### 4.0 Criteria Management Endpoints

- [ ] 4.1 Update criterion passed status (manual toggle)
  ```
  PATCH /api/capabilities/features/{feature_id}/acceptance-criteria/{criterion_id}
  Body: {"passed": true, "verified_by": "manual"}
  ```

- [ ] 4.2 Get verification summary stats
  ```
  GET /api/capabilities/features/verification-summary
  Response: {
    "total_criteria": 328,
    "passed": 142,
    "failed": 45,
    "pending": 141,
    "by_type": {
      "api": {"total": 180, "passed": 120, "failed": 30, "pending": 30},
      "ui": {"total": 100, "passed": 20, "failed": 10, "pending": 70},
      "test": {"total": 20, "passed": 2, "failed": 5, "pending": 13},
      ...
    },
    "last_run_at": "2025-12-06T05:00:00Z"
  }
  ```

- [ ] 4.3 Get verification history
  ```
  GET /api/capabilities/verification-history
  Response: [
    {"run_at": "...", "passed": 142, "failed": 45, "pending": 141},
    ...
  ]
  ```

### 4.1 Claude Code-Optimized Endpoints

Design principle: **Claude Code should be able to assess feature/criteria status with simple curl commands during development.**

- [ ] 4.4 Get failing criteria (for quick triage)
  ```
  GET /api/capabilities/criteria/failing
  Response: [
    {
      "feature_id": "FEAT-015",
      "feature_name": "Market Intelligence Narrative",
      "criterion_id": "ac-001",
      "criterion": "API returns narrative",
      "verification": "curl ...",
      "verification_output": "404 Not Found",
      "failed_at": "2025-12-06T05:00:00Z"
    },
    ...
  ]
  ```

- [ ] 4.5 Get pending criteria by type (for batch verification)
  ```
  GET /api/capabilities/criteria/pending?type=api
  GET /api/capabilities/criteria/pending?type=test
  GET /api/capabilities/criteria/pending?type=ui
  Response: [{feature_id, criterion_id, criterion, verification}, ...]
  ```

- [ ] 4.6 Get feature verification status (single feature check)
  ```
  GET /api/capabilities/features/{feature_id}/verification-status
  Response: {
    "feature_id": "FEAT-015",
    "name": "Market Intelligence Narrative",
    "criteria_total": 2,
    "criteria_passed": 1,
    "criteria_failed": 1,
    "criteria_pending": 0,
    "all_passing": false,
    "criteria": [
      {"id": "ac-001", "passed": true, "verified_at": "..."},
      {"id": "ac-002", "passed": false, "verified_at": "...", "output": "..."}
    ]
  }
  ```

- [ ] 4.7 Bulk verify by feature IDs (for targeted verification)
  ```
  POST /api/capabilities/verify-batch
  Body: {"feature_ids": ["FEAT-015", "FEAT-016", "FEAT-017"]}
  Response: {"queued": 3, "estimated_seconds": 30}
  ```

- [ ] 4.8 Get criteria by vision goal (for goal-focused development)
  ```
  GET /api/capabilities/criteria/by-vision-goal/VG-INTEL
  Response: {
    "goal": "VG-INTEL",
    "goal_name": "Market Intelligence",
    "total_criteria": 45,
    "passed": 30,
    "failed": 5,
    "pending": 10,
    "features": [{"feature_id": "FEAT-015", "passed": 1, "failed": 1}, ...]
  }
  ```

---

## Phase 5: Slash Command Updates

### 5.0 Update /audit_it Command

- [ ] 5.1 Add criteria verification summary to audit output
  ```markdown
  ## Acceptance Criteria Status
  - Total: 328 criteria across 164 features
  - Passing: 142 (43%)
  - Failing: 45 (14%)  ← ATTENTION NEEDED
  - Pending: 141 (43%)

  ### Failing Criteria (Top 10)
  | Feature | Criterion | Last Output |
  |---------|-----------|-------------|
  | FEAT-015 | ac-001 | 404 Not Found |
  ...
  ```

- [ ] 5.2 Add --verify flag to trigger verification run
  ```
  /audit_it --verify  → Run full verification before audit
  ```

- [ ] 5.3 Add --failing flag to show only failing criteria
  ```
  /audit_it --failing  → Show only features with failing criteria
  ```

### 5.1 Update /verify_it Command

- [ ] 5.4 Enhance /verify_it to use acceptance criteria
  ```
  /verify_it FEAT-015
  → Runs all criteria verifications for FEAT-015
  → Shows pass/fail for each criterion
  → Updates database with results
  ```

- [ ] 5.5 Add batch mode for multiple features
  ```
  /verify_it FEAT-015 FEAT-016 FEAT-017
  → Verifies all three features
  ```

- [ ] 5.6 Add type filter
  ```
  /verify_it --type=api   → Only verify API criteria
  /verify_it --type=test  → Only verify test criteria
  ```

### 5.2 Update /check_it Command

- [ ] 5.7 Include criteria status in feature check
  ```
  /check_it

  ## Feature Status
  | Feature | Passes | Tasks | Criteria |
  |---------|--------|-------|----------|
  | FEAT-015 | null | 2/5 | 1/2 ⚠️ |
  ...
  ```

- [ ] 5.8 Add criteria-focused mode
  ```
  /check_it --criteria
  → Focus on acceptance criteria status only
  → Group by vision goal
  ```

### 5.3 Update /do_it Command

- [ ] 5.9 Add post-task verification option
  ```
  After completing a feature's tasks, prompt:
  "Run acceptance criteria verification? [Y/n]"
  ```

- [ ] 5.10 Show criteria status when selecting features to work on
  ```
  Features to work on:
  1. FEAT-015 (Market Intelligence) - 1/2 criteria passing
  2. FEAT-016 (Fear & Greed Gauge) - 2/2 criteria passing ✓
  ```

### 5.4 Update /task_it Command

- [ ] 5.11 When creating new features, prompt for acceptance criteria
  ```
  /task_it Add dark mode support

  → Creates FEAT-XXX
  → Prompts: "Add acceptance criteria? [Y/n]"
  → If yes, prompts for 2+ testable criteria
  ```

- [ ] 5.12 Validate criteria have verification commands
  ```
  Warning: Criterion "Dark mode toggle works" has no verification command.
  Add verification? (e.g., "screenshot /settings showing dark mode toggle")
  ```

---

## Phase 6: UI Updates

### 6.0 Features Tab Enhancements

- [ ] 6.1 Add verification status column to feature table
  - Show "3/4 passing" or checkmark if all pass
  - Color coding: green=all pass, yellow=partial, red=failures

- [ ] 6.2 Add expandable criteria section in feature row
  - List each criterion with pass/fail/pending icon
  - Show verification timestamp
  - "Verify" button for individual criteria
  - "Mark as Verified" toggle for manual criteria

- [ ] 6.3 Add verification output viewer
  - Click criterion to see last verification output
  - For UI criteria, show screenshot thumbnail

### 6.1 Summary Dashboard Cards

- [ ] 6.4 Add verification summary card to Capabilities page
  ```
  ┌─────────────────────────────────┐
  │ Acceptance Criteria             │
  │ ═══════════════════════════════ │
  │ 142 / 328 passing (43%)         │
  │ ▓▓▓▓▓▓▓░░░░░░░░░               │
  │                                 │
  │ API: 120/180 (67%)              │
  │ UI:   20/100 (20%)              │
  │ Test:  2/20  (10%)              │
  │                                 │
  │ Last verified: 2h ago           │
  │ [Verify All] [View Details]     │
  └─────────────────────────────────┘
  ```

- [ ] 6.5 Add "Verify All" button with progress indicator

### 6.2 Vision Goals Tab (New Tab in Capabilities)

- [ ] 6.6 Create Vision Goals tab component
  ```
  frontend/components/capabilities/VisionGoalsTab.tsx
  ```

- [ ] 6.7 Vision Goals table with columns:
  - Code (VG-INTEL, VG-AUTO, etc.)
  - Name (Market Intelligence, Autonomous Operation, etc.)
  - Description (from VISION.md)
  - Feature Count (how many features have this goal)
  - Criteria Status (passed/total with percentage)
  - Last Updated

- [ ] 6.8 Add expandable row showing features linked to goal
  - Click goal row to see all features with that vision goal
  - Show feature name, passes status, criteria status

- [ ] 6.9 Add/Edit/Delete vision goals
  - Add Goal button opens form dialog
  - Edit button for existing goals
  - Delete with confirmation (warn if features linked)

- [ ] 6.10 Add vision goals filter to Features tab
  - Dropdown to filter features by vision goal
  - Vision goal badges on feature rows (clickable to filter)

### 6.3 Vision Goals API Endpoints

- [ ] 6.11 CRUD endpoints for vision goals
  ```
  GET    /api/vision-goals              → List all goals with stats
  GET    /api/vision-goals/{code}       → Single goal with linked features
  POST   /api/vision-goals              → Create new goal
  PATCH  /api/vision-goals/{code}       → Update goal
  DELETE /api/vision-goals/{code}       → Delete goal (if no features linked)
  ```

- [ ] 6.12 Vision goals summary endpoint
  ```
  GET /api/vision-goals/summary
  Response: {
    "total_goals": 7,
    "goals": [
      {
        "code": "VG-INTEL",
        "name": "Market Intelligence",
        "feature_count": 45,
        "criteria_passed": 30,
        "criteria_total": 45,
        "pass_rate": 0.67
      },
      ...
    ]
  }
  ```

### 6.4 Reorder Capabilities Tabs (Strategic → Tactical → Infrastructure)

- [ ] 6.13 Reorder tabs in capabilities page.tsx
  ```
  Current order (unclear hierarchy):
  Features | Database | Tasks | API | Sources | Rules | Gaps | Insights

  New order (strategic → tactical → infrastructure):
  1. Dashboard     - High-level summary, health overview
  2. Vision Goals  - Strategic "why" (NEW)
  3. Features      - Implementation of goals
  4. Sources       - Data providers powering features
  5. Rules         - Trading rules governing behavior
  6. Database      - Infrastructure: tables, freshness
  7. Tasks         - Infrastructure: Celery scheduled tasks
  8. API           - Infrastructure: endpoint health
  9. Gaps          - What's missing
  10. Insights     - AI observations
  ```

- [ ] 6.14 Update tab navigation component with new order

### 6.5 Archive VISION.md (Database is Source of Truth)

- [ ] 6.15 Migrate VISION.md content to database
  - Extract all goals with full descriptions
  - Extract principles and mission statement (store as special goals or separate table)
  - Populate vision_goals table with complete data

- [ ] 6.16 Archive VISION.md to docs/archive/
  ```
  mv docs/core/VISION.md docs/archive/VISION-legacy.md
  ```

- [ ] 6.17 Update CLAUDE.md to reference Vision Goals tab
  - Remove VISION.md from documentation map
  - Add note: "Vision goals viewable/editable at /capabilities → Vision Goals tab"

- [ ] 6.18 Add "Export to Markdown" button in Vision Goals tab
  - Generates VISION.md-style document from database
  - For external sharing or documentation purposes

---

## Phase 7: Verification & Testing

### 7.0 Test the Verification System

- [ ] 7.1 Run verification on 10 sample API criteria
- [ ] 7.2 Run verification on 5 sample test criteria
- [ ] 7.3 Run verification on 5 sample UI criteria
- [ ] 7.4 Test manual toggle for backend criteria
- [ ] 7.5 Verify summary stats are accurate

### 7.1 Integration Tests

- [ ] 7.6 Add pytest tests for criteria_verifier.py
- [ ] 7.7 Add pytest tests for verification endpoints
- [ ] 7.8 Add pytest tests for scheduled task

---

## Technical Notes

### Verification Command Patterns

**API criteria** (auto-verifiable):
```
curl -s http://localhost:8000/api/health | jq '.status'
curl -s http://localhost:8000/api/features | jq '.total'
```

**Test criteria** (auto-verifiable):
```
pytest tests/agents/test_rules_validator.py
pytest tests/ -k "test_watchlist"
```

**UI criteria** (auto-verifiable via browser):
```
screenshot /dashboard showing Fear & Greed gauge
screenshot /watchlist with row expanded
```

**Backend/Quality criteria** (manual only):
```
Code review: backend/app/llm/provider.py has LLMProvider class
Verify scheduled task in beat_schedule
```

### Safety Considerations

1. **Command execution sandboxing**
   - Only allow whitelisted command patterns
   - No shell=True, use subprocess with args list
   - Timeout all executions

2. **Resource limits**
   - Max 10 concurrent verifications
   - Max 60s per test criterion
   - Max 10s per API criterion
   - Max 30s per UI criterion

3. **Output truncation**
   - Store max 1000 chars of verification_output
   - Store max 5 screenshots per run

---

## Files to Create/Modify

**New files:**
- `backend/app/services/criteria_verifier.py` - Verification engine
- `backend/app/tasks/verify_criteria.py` - Celery task
- `backend/app/api/vision_goals_router.py` - Vision goals CRUD API
- `migrations/XXX_add_criteria_verification_fields.py` - Schema migration
- `migrations/XXX_create_vision_goals_table.py` - Vision goals table
- `frontend/components/capabilities/CriteriaVerificationCard.tsx` - Summary card
- `frontend/components/capabilities/CriterionRow.tsx` - Individual criterion display
- `frontend/components/capabilities/VisionGoalsTab.tsx` - Vision goals tab
- `frontend/components/capabilities/VisionGoalRow.tsx` - Expandable goal row
- `docs/archive/VISION-legacy.md` - Archived original VISION.md

**Modified files:**
- `backend/app/api/capabilities/features_router.py` - New endpoints
- `backend/app/celery_app.py` - Add scheduled task
- `frontend/components/capabilities/FeaturesTab.tsx` - Add verification column, goal badges
- `frontend/app/capabilities/page.tsx` - Add Vision Goals tab
- `CLAUDE.md` - Update documentation map (remove VISION.md, add Vision Goals tab reference)

**Slash commands to update:**
- `.claude/commands/audit_it.md` - Add criteria summary, --verify flag, --failing flag
- `.claude/commands/verify_it.md` - Leverage acceptance criteria verification
- `.claude/commands/check_it.md` - Include criteria status in feature check
- `.claude/commands/do_it.md` - Post-task verification prompt, criteria display
- `.claude/commands/task_it.md` - Prompt for acceptance criteria on new features

---

## Execution Order

0. **Phase 0** FIRST (MANDATORY) - scope discovery with explore agents
   - Must complete before ANY implementation
   - Run 3+ explore agents in parallel (very thorough)
   - Adjust task list based on findings
   - Get user approval at checkpoint 0.7
1. **Phase 1** - schema changes are foundational
2. **Phase 2** - verification engine
3. **Phase 3** - scheduled task depends on engine
4. **Phase 4** - API endpoints (including Claude-optimized ones)
5. **Phase 5** - Slash command updates (can use API endpoints)
6. **Phase 6** - UI depends on API
7. **Phase 7** - testing validates everything

---

## API Quick Reference (for Claude Code)

During development, use these endpoints to check verification status:

```bash
# Get summary stats
curl -s http://localhost:8000/api/capabilities/features/verification-summary | jq

# Get failing criteria (what to fix)
curl -s http://localhost:8000/api/capabilities/criteria/failing | jq

# Get pending criteria by type
curl -s http://localhost:8000/api/capabilities/criteria/pending?type=api | jq

# Check specific feature
curl -s http://localhost:8000/api/capabilities/features/FEAT-015/verification-status | jq

# Verify a batch of features
curl -X POST http://localhost:8000/api/capabilities/verify-batch \
  -H 'Content-Type: application/json' \
  -d '{"feature_ids": ["FEAT-015", "FEAT-016"]}'

# Get criteria by vision goal
curl -s http://localhost:8000/api/capabilities/criteria/by-vision-goal/VG-INTEL | jq

# Vision Goals API
curl -s http://localhost:8000/api/vision-goals | jq                    # List all
curl -s http://localhost:8000/api/vision-goals/VG-INTEL | jq           # Single goal + linked features
curl -s http://localhost:8000/api/vision-goals/summary | jq            # Stats per goal
```

---

**Version**: 1.3.0 | **Created**: 2025-12-06 | **Updated**: 2025-12-06 (Phases 0-6 complete)

---

## Phase 5-6 Implementation Notes (Completed)

### Phase 5: Slash Command Updates ✅
- Updated `/audit_it` with `--verify` and `--failing` flags
- Updated `/check_it` with `--criteria` mode for criteria-focused reporting
- Both commands now include verification summary in output

### Phase 6: UI Updates ✅
**FeaturesTab Enhancements:**
- Added verification summary query and display
- Shows total criteria, passed, failed, pending counts
- Breakdown by type (api, ui, test, backend, etc.)

**VisionGoalsTab (New Component):**
- New tab at `/capabilities` → Vision
- Shows all 7 vision goals from VISION.md
- Expandable rows showing linked features per goal
- Pass rate progress bars
- Criteria passed/total counts per goal

**Files Created/Modified:**
- `frontend/components/capabilities/FeaturesTab.tsx` - verification summary card
- `frontend/components/capabilities/VisionGoalsTab.tsx` - new component
- `frontend/app/capabilities/page.tsx` - Vision tab added

### Remaining: Phase 7 (Testing)
- Integration tests for criteria_verifier.py
- E2E tests for verification endpoints
