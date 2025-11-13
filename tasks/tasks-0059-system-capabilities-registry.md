# Task List: System Capabilities Registry (Three-Phase Intelligence)

**Source**: PRD - tasks/prd-system-capabilities.md
**Complexity**: Complex
**Effort**: HIGH (20-24 hours sequential, 10-12 hours with parallel agents)
**Environment**: Local Dev (auto-detected)
**Created**: 2025-11-13 22:35

---

## Summary

**Goal**: Build an intelligent, self-updating registry that auto-discovers data sources (DB tables, Celery tasks, APIs), AI analyzes completeness/freshness/gaps, and humans add strategic context. Prevents AI agents from breaking features due to incomplete context.

**Approach**: Three-phase system:
1. Automated scanning (scripts → normalized tables)
2. AI analysis (Claude/Gemini API → insights with severity/impact/fixes)
3. Human review (confirm/dismiss insights, add strategic notes)

**Scope Discovery**: Required (medium exploration) - Understand existing scanning patterns, AI integration, database schema conventions

---

## Tasks

### 0.0 Scope Discovery & Architecture Review (MANDATORY)

- [ ] 0.1 Run Explore subagent in "medium" mode
  - Pattern: Existing capability scanning (if any), database schema patterns, AI integration patterns
  - Goal: Understand conventions for new table schemas, Celery task patterns, AI API usage
  - Search: backend/app/storage/, backend/app/tasks/, backend/scripts/scan_capabilities.py (existing prototype)
  - Output: Findings on schema conventions, existing scanning code, AI integration examples
- [ ] 0.2 Review existing prototype
  - File: backend/scripts/scan_capabilities.py (created earlier in session)
  - File: backend/scripts/CAPABILITIES_SCAN_README.md
  - Extract reusable code for Phase 1 implementation
- [ ] 0.3 Checkpoint: Confirm architecture decisions
  - Table naming conventions: Confirmed
  - Config file format: YAML vs JSON
  - AI API choice: Claude Sonnet 4.5 vs Gemini 2.0
  - UI framework: Existing Next.js/React patterns

**DO NOT PROCEED TO TASK 1 UNTIL ARCHITECTURE CONFIRMED**

---

### 1.0 Database Schema & Migrations (Phase 1 Foundation)

- [ ] 1.1 Create migration: Core capability tables
  - File: `backend/alembic/versions/035_system_capabilities_tables.sql`
  - Tables: `db_capabilities`, `celery_capabilities`, `api_capabilities`
  - Indexes: category, freshness_status, success_rate_pct
  - Reference PRD section 1.1 for complete schema
- [ ] 1.2 Create migration: AI insights table
  - File: `backend/alembic/versions/036_capability_insights.sql`
  - Table: `capability_insights`
  - Indexes: capability_type+id, status, severity
  - Foreign keys: capability_id references (polymorphic via type)
- [ ] 1.3 Create migration: Human notes table
  - File: `backend/alembic/versions/037_capability_notes.sql`
  - Table: `capability_notes`
  - Foreign key: insight_id references capability_insights
  - Indexes: capability_type+id, insight_id
- [ ] 1.4 Run migrations on local database
  - Verify all tables created successfully
  - Check indexes exist
  - Verify foreign key constraints work

---

### 2.0 Configuration System (YAML-Based)

- [ ] 2.1 Create configuration file structure
  - File: `backend/app/config/capabilities_config.yaml`
  - Sections: scan_config, targets (db, celery, api), ai_analysis, categorization
  - Reference PRD section 2 for complete config structure
- [ ] 2.2 Create config loader service
  - File: `backend/app/services/config_loader.py`
  - Function: `load_capabilities_config()` → returns dict
  - Validate required fields present
  - Cache config (reload only on file change)
- [ ] 2.3 Add config to app initialization
  - Import in `backend/app/main.py`
  - Load on startup, log confirmation
  - Handle missing/invalid config gracefully

---

### 3.0 Database Scanner (Auto-Discovery)

- [ ] 3.1 Refactor existing prototype into production code
  - Source: `backend/scripts/scan_capabilities.py`
  - Target: `backend/app/services/capability_scanner.py`
  - Class: `DatabaseScanner(config)`
- [ ] 3.2 Implement table scanning logic
  - Method: `scan_tables()` → list of db_capability dicts
  - Detect: row_count, columns, columns_with_data, columns_mostly_null
  - Calculate: completeness_pct, date_range_start/end
  - Use config for expected_freshness mapping
- [ ] 3.3 Implement freshness calculation
  - Method: `calculate_freshness_status(table_name, days_since_update, expected)`
  - Logic: current (<1 day), acceptable (1-2 days), stale (3-7 days), critical (>7 days)
  - Adjust based on expected_freshness from config
- [ ] 3.4 Implement categorization
  - Method: `categorize_table(table_name, config)`
  - Match table name against config categorization patterns
  - Default to 'infrastructure' if no match
- [ ] 3.5 Add upsert logic for db_capabilities
  - Method: `save_db_capabilities(capabilities)`
  - Use `ON CONFLICT (table_name) DO UPDATE`
  - Update last_scanned_at timestamp
  - Log changes (new tables, removed tables)

---

### 4.0 Celery Task Scanner (Scheduled Tasks)

- [ ] 4.1 Create Celery scanner service
  - File: `backend/app/services/capability_scanner.py` (add to existing)
  - Class method: `CeleryScanner(config)`
- [ ] 4.2 Implement beat schedule scanning
  - Method: `scan_beat_schedule()` → list of celery_capability dicts
  - Source: `celery_app.conf.beat_schedule`
  - Extract: task_name, schedule, task_path, function_name
- [ ] 4.3 Parse schedule into human-readable format
  - Method: `parse_schedule(schedule_obj)` → description string
  - Handle crontab: "Daily at 04:00 UTC"
  - Handle intervals: "Every 60 seconds"
  - Calculate interval_seconds for sorting
- [ ] 4.4 Query Celery task metadata (if available)
  - Table: `celery_taskmeta` (if using DB backend)
  - Get: last_run_at, success_count_7d, failure_count_7d
  - Calculate: success_rate_pct, avg_duration_ms
  - Fallback: Set to NULL if celery_taskmeta not available
- [ ] 4.5 Detect task dependencies (basic)
  - Method: `detect_populates_tables(task_path)` → list of table names
  - Read task file, search for INSERT/UPDATE statements
  - Regex: `(INSERT INTO|UPDATE)\s+([a-z_]+)`
  - Store in populates_tables JSONB field
- [ ] 4.6 Add upsert logic for celery_capabilities
  - Use `ON CONFLICT (task_name) DO UPDATE`
  - Update last_scanned_at
  - Log changes

---

### 5.0 API Scanner (Endpoint Discovery)

- [ ] 5.1 Create API scanner service
  - File: `backend/app/services/capability_scanner.py` (add to existing)
  - Class method: `APIScanner(config)`
- [ ] 5.2 Implement route file scanning
  - Method: `scan_api_routes()` → list of api_capability dicts
  - Directory: `backend/app/routes/`
  - Pattern: `@router.(get|post|put|delete)\([\'"]([^\'"]+)[\'"]\)`
  - Extract: endpoint_path, http_method, route_file, function_name
- [ ] 5.3 Detect API dependencies (basic)
  - Method: `detect_depends_on_tables(route_file, function_name)`
  - Read function body, search for table references
  - Pattern: `FROM ([a-z_]+)` or `conn.execute.*FROM\s+([a-z_]+)`
  - Store in depends_on_tables JSONB field
- [ ] 5.4 Add upsert logic for api_capabilities
  - Use `ON CONFLICT (endpoint_path, http_method) DO UPDATE`
  - Note: Response time metrics = NULL for Phase 1 (add middleware later)

---

### 6.0 Main Scan Script & Celery Task (Orchestration)

- [ ] 6.1 Create main scan script
  - File: `backend/scripts/scan_capabilities_v2.py` (production version)
  - Load config
  - Run DatabaseScanner, CeleryScanner, APIScanner
  - Aggregate results
  - Call save methods
  - Log summary (tables: X, tasks: Y, APIs: Z, new: A, changed: B)
- [ ] 6.2 Make script runnable standalone
  - `if __name__ == '__main__':` entry point
  - CLI args: `--output json|text`, `--diff`
  - Test: `python backend/scripts/scan_capabilities_v2.py`
- [ ] 6.3 Create Celery task wrapper
  - File: `backend/app/tasks/capability_tasks.py`
  - Task: `@celery_app.task(name="scan_system_capabilities")`
  - Call main scan script logic
  - Log results
  - Store scan timestamp in db_capabilities.last_scanned_at
- [ ] 6.4 Add to Celery beat schedule
  - File: `backend/app/celery_app.py`
  - Schedule: Daily at 03:00 UTC (after data refresh tasks)
  - Verify task appears in `celery -A app.celery_app inspect registered`

---

### 7.0 AI Analyzer Service (Phase 2 - AI Insights)

- [ ] 7.1 Create AI analyzer base service
  - File: `backend/app/services/ai_analyzer.py`
  - Class: `CapabilityAnalyzer(config)`
  - Method: `analyze()` → list of insight dicts
- [ ] 7.2 Implement data loading methods
  - Method: `load_capabilities()` → fetch all from db_capabilities, celery_capabilities, api_capabilities
  - Method: `load_error_logs(hours=24)` → read recent logs (parse /var/log/portfolio-ai/*.log)
  - Method: `load_task_files()` → read tasks/*.md files for context
- [ ] 7.3 Build AI prompt template
  - Method: `build_prompt(capabilities, logs, task_files)` → string
  - Template: See PRD section 4.2 for complete prompt structure
  - Include: DB capabilities JSON, Celery tasks JSON, error logs, task file content
  - Format: Structured instructions for AI to analyze and return JSON insights
- [ ] 7.4 Implement AI API integration
  - Method: `call_ai_api(prompt)` → raw response string
  - Use: Anthropic SDK for Claude Sonnet 4.5
  - Config: Model name from capabilities_config.yaml
  - Handle: API errors, rate limits, timeouts
  - Fallback: Return empty list if AI unavailable
- [ ] 7.5 Parse and validate AI response
  - Method: `parse_ai_response(response)` → list of insight dicts
  - Expect: JSON array of insight objects
  - Validate: Required fields (finding, severity, impact, suggested_fix)
  - Filter: confidence_threshold from config (default: 0.70)
  - Deduplicate: Similar insights (same table + insight_type)
- [ ] 7.6 Store insights in database
  - Method: `save_insights(insights)`
  - Insert into `capability_insights` table
  - Use `ON CONFLICT (capability_type, capability_id, insight_type) DO UPDATE`
  - Update: finding, severity, updated_at
  - Preserve: status (don't overwrite if confirmed/dismissed)

---

### 8.0 AI Analysis Celery Task (Automated Execution)

- [ ] 8.1 Create AI analysis task
  - File: `backend/app/tasks/capability_tasks.py` (add to existing)
  - Task: `@celery_app.task(name="analyze_capabilities")`
  - Instantiate CapabilityAnalyzer
  - Run analyze()
  - Save insights
  - Log summary (insights generated: X, critical: Y, high: Z)
- [ ] 8.2 Add to Celery beat schedule
  - File: `backend/app/celery_app.py`
  - Schedule: Daily at 03:15 UTC (15 min after capability scan)
  - Dependency: Runs after scan_system_capabilities completes
- [ ] 8.3 Test AI analysis manually
  - Trigger: `celery -A app.celery_app call analyze_capabilities`
  - Verify: Insights appear in capability_insights table
  - Check: Confidence scores, severity levels, suggested fixes
  - Validate: References field has file paths/table names

---

### 9.0 API Endpoints (Backend Routes)

- [ ] 9.1 Create capabilities routes file
  - File: `backend/app/routes/capabilities.py`
  - Router: `router = APIRouter(prefix="/api/capabilities", tags=["capabilities"])`
- [ ] 9.2 Implement GET /api/capabilities
  - Query params: type (db|celery|api|all), category, status, limit, offset
  - Response: { total, capabilities: [...] }
  - Join: Include related insights count, notes count
  - Filter: By type, category, freshness_status
  - Paginate: Default limit=50, max=200
- [ ] 9.3 Implement GET /api/capabilities/{type}/{id}
  - Path params: type (db|celery|api), id (integer)
  - Response: { capability, insights, notes, dependencies }
  - Dependencies: Basic - populated_by, used_by from JSONB fields
- [ ] 9.4 Implement GET /api/capabilities/insights
  - Query params: status, severity, type, limit, offset
  - Response: { total, insights: [...] }
  - Join: Include related capability info (table_name, task_name)
  - Filter: By status (pending|confirmed|dismissed), severity
- [ ] 9.5 Implement POST /api/capabilities/insights/{id}/review
  - Body: { status, status_reason, reviewed_by }
  - Update: capability_insights.status, status_reason, reviewed_at, reviewed_by
  - Validate: status in (confirmed, dismissed, in_progress, fixed)
- [ ] 9.6 Implement POST /api/capabilities/notes
  - Body: { capability_type, capability_id, insight_id, note_type, note }
  - Insert: capability_notes table
  - created_by: Extract from auth or default to 'human'
- [ ] 9.7 Implement GET /api/capabilities/notes
  - Query params: capability_type, capability_id, insight_id
  - Response: { notes: [...] }
- [ ] 9.8 Register routes in main app
  - File: `backend/app/main.py`
  - Import: `from app.routes import capabilities`
  - Include: `app.include_router(capabilities.router)`
- [ ] 9.9 Test all API endpoints
  - Use curl or pytest to verify each endpoint
  - Test filters, pagination, edge cases
  - Verify CORS settings allow frontend access

---

### 10.0 Frontend - Main Capabilities Page (UI Overview)

- [ ] 10.1 Create capabilities page component
  - File: `frontend/app/capabilities/page.tsx`
  - Route: `/capabilities`
  - Layout: Header, tabs, table/cards
- [ ] 10.2 Implement API client hooks
  - File: `frontend/lib/api/capabilities.ts`
  - Functions: `fetchCapabilities(params)`, `fetchInsights(params)`, `fetchNotes(params)`
  - Use: fetch() or existing API client pattern
  - Handle: Loading states, errors, pagination
- [ ] 10.3 Create capabilities table component
  - File: `frontend/components/capabilities/CapabilitiesTable.tsx`
  - Props: capabilities[], onSelect, filters
  - Columns: Category (icon), Name, Source, Coverage, Status badges
  - Features: Sort, filter, search, pagination
- [ ] 10.4 Add status badge components
  - File: `frontend/components/capabilities/StatusBadge.tsx`
  - Types: Freshness (current/stale/critical), Completeness (%), Insights (count)
  - Colors: Green (✅), Yellow (⚠️), Red (🔴)
- [ ] 10.5 Implement category filter dropdown
  - Options: All, Market Data, News, Portfolio, Analytics, Infrastructure
  - Icon per category: 🔵 💰 📰 📈 🔬 ⚙️
- [ ] 10.6 Add search/filter bar
  - Search: By name, source, notes content
  - Filters: Type (db/celery/api), Status (current/stale), Category
- [ ] 10.7 Add refresh scan button
  - Trigger: POST /api/admin/scan-capabilities (create admin endpoint)
  - Show: Loading spinner during scan
  - Update: Table data after scan completes

---

### 11.0 Frontend - Detail View (Modal/Panel)

- [ ] 11.1 Create capability detail modal
  - File: `frontend/components/capabilities/CapabilityDetailModal.tsx`
  - Trigger: Click row in table
  - Layout: Header, tabs (Overview, Insights, Notes, Dependencies)
- [ ] 11.2 Implement Overview tab
  - Display: All capability fields (row_count, columns, date_range, etc.)
  - For DB: Show columns_with_data (✅) vs columns_null (❌)
  - For Celery: Show schedule, last_run, success_rate
  - For API: Show endpoint, method, dependencies
- [ ] 11.3 Implement Insights tab
  - Fetch: GET /api/capabilities/insights?capability_type={type}&capability_id={id}
  - Display: List of AI insights with severity badges
  - Show: Finding, Impact, Suggested Fix, Confidence %
  - Actions: [✓ Confirm] [✗ Dismiss] [💬 Add Note] buttons
- [ ] 11.4 Implement Notes tab
  - Fetch: GET /api/capabilities/notes?capability_type={type}&capability_id={id}
  - Display: List of notes with type, author, timestamp
  - Form: Add new note (textarea, note_type dropdown, submit)
  - Actions: Edit/delete existing notes
- [ ] 11.5 Implement Dependencies tab (basic)
  - Display: populated_by (tasks), used_by (APIs, UI features)
  - Source: JSONB fields from capability record
  - Format: Clickable links to related capabilities
- [ ] 11.6 Add insight review actions
  - Confirm button: POST /api/capabilities/insights/{id}/review { status: 'confirmed' }
  - Dismiss button: POST /api/capabilities/insights/{id}/review { status: 'dismissed' }
  - Prompt for status_reason (textarea)
  - Update UI after action completes

---

### 12.0 Frontend - AI Insights Tab (Phase 2 Focus)

- [ ] 12.1 Create AI insights page/tab
  - File: `frontend/components/capabilities/InsightsTab.tsx`
  - Fetch: GET /api/capabilities/insights
  - Filter: By status (pending/confirmed/dismissed), severity
- [ ] 12.2 Group insights by severity
  - Sections: 🔴 CRITICAL, ⚠️ HIGH, 📊 MEDIUM, ℹ️ LOW
  - Show count per section
  - Collapsible sections
- [ ] 12.3 Create insight card component
  - File: `frontend/components/capabilities/InsightCard.tsx`
  - Display: Severity badge, finding, impact, suggested fix, confidence
  - Show: Related capability (link to detail view)
  - Actions: Confirm, Dismiss, Add Note
- [ ] 12.4 Add bulk actions
  - Select multiple insights (checkbox)
  - Bulk confirm/dismiss
  - Useful for dismissing multiple low-priority insights

---

### 13.0 Frontend - Gaps Tab (Missing Capabilities)

- [ ] 13.1 Create gaps tab component
  - File: `frontend/components/capabilities/GapsTab.tsx`
  - Fetch: GET /api/capabilities/insights?insight_type=missing_capability
  - Display: AI-identified missing data sources
- [ ] 13.2 Group gaps by category
  - Sections: Market Data, News, Portfolio, Analytics
  - Show: Why needed, Impact, Priority (from AI)
- [ ] 13.3 Add gap management actions
  - Button: [+ Add to Roadmap] → Creates task file or adds to WORK_TRACKER
  - Button: [Dismiss - Not Trading This] → Marks insight as dismissed with reason
  - Note field: Add strategic context about why gap exists

---

### 14.0 Testing & Quality Assurance

- [ ] 14.1 Write unit tests for database scanner
  - File: `backend/tests/unit/test_capability_scanner.py`
  - Test: Table scanning, completeness calculation, freshness status
  - Mock: Database queries
  - Coverage: 80%+ for scanner logic
- [ ] 14.2 Write unit tests for Celery scanner
  - Test: Beat schedule parsing, human-readable format, dependency detection
  - Mock: celery_app.conf.beat_schedule
- [ ] 14.3 Write unit tests for AI analyzer
  - Test: Prompt building, response parsing, confidence filtering
  - Mock: AI API calls
  - Test: Invalid JSON handling, missing fields
- [ ] 14.4 Write integration tests for API endpoints
  - File: `backend/tests/integration/test_capabilities_api.py`
  - Test: All GET/POST endpoints
  - Verify: Filters, pagination, joins
  - Test: Review workflow (confirm/dismiss insights)
- [ ] 14.5 Write integration test for full scan
  - Test: Run scan_system_capabilities task
  - Verify: Tables populated correctly
  - Check: Row counts match expected
  - Validate: Freshness status calculated correctly
- [ ] 14.6 Write frontend component tests
  - File: `frontend/components/capabilities/__tests__/CapabilitiesTable.test.tsx`
  - Test: Rendering, filtering, sorting
  - Mock: API responses
  - Use: React Testing Library
- [ ] 14.7 Run full test suite
  - Backend: `cd backend && pytest tests/ -v`
  - Frontend: `cd frontend && npm test`
  - Verify: All tests pass, no regressions
- [ ] 14.8 Run linting and type checks
  - Backend: `~/portfolio-ai/scripts/lint.sh`
  - Fix: Any ruff or mypy errors
  - Verify: No new `Any` types introduced

---

### 15.0 Integration & Deployment

- [ ] 15.1 Verify migrations on test database
  - Run: All 3 migrations (035, 036, 037)
  - Check: Tables exist, indexes created
  - Test: Foreign key constraints work
- [ ] 15.2 Run initial capability scan
  - Trigger: `celery -A app.celery_app call scan_system_capabilities`
  - Verify: db_capabilities, celery_capabilities, api_capabilities populated
  - Check: Row counts (expect ~30 tables, ~11 tasks, ~10 APIs)
- [ ] 15.3 Run initial AI analysis
  - Trigger: `celery -A app.celery_app call analyze_capabilities`
  - Verify: capability_insights populated
  - Check: Insights generated for known issues (Fear & Greed stale data, etc.)
  - Review: AI findings make sense
- [ ] 15.4 Restart services
  - Run: `bash ~/portfolio-ai/scripts/restart.sh`
  - Verify: Backend starts without errors
  - Check: Celery beat schedule includes new tasks
  - Monitor: First scheduled scan runs successfully (next day at 03:00 UTC)
- [ ] 15.5 Test frontend UI manually
  - Navigate: http://192.168.8.233:3000/capabilities
  - Verify: Table loads, shows capabilities
  - Test: Filters, search, pagination work
  - Open: Detail modal, verify all tabs load
  - Test: Review insights (confirm/dismiss)
  - Test: Add note, verify it saves
- [ ] 15.6 Verify AI agent integration
  - Test: Query API from command line
  - Example: `curl http://localhost:8000/api/capabilities?type=db&table=fear_greed_components | jq`
  - Verify: Returns capability data + insights
  - Check: AI can use this during refactoring

---

### 16.0 Documentation & Final Touches

- [ ] 16.1 Update CLAUDE.md with AI integration guide
  - Section: "Querying System Capabilities Before Refactoring"
  - Example: How to check capabilities API before making changes
  - Checklist: Pre-refactoring steps (query capabilities, read insights, check notes)
- [ ] 16.2 Create user documentation
  - File: `docs/reference/system-capabilities.md`
  - Sections: What is this, How to use, Reviewing AI insights, Adding notes
  - Screenshots: Main page, detail modal, insights tab
- [ ] 16.3 Update API reference docs
  - File: `docs/core/API_REFERENCE.md`
  - Add: Capabilities endpoints documentation
  - Include: Request/response examples
- [ ] 16.4 Add configuration documentation
  - Document: capabilities_config.yaml structure
  - Explain: expected_freshness values, categorization patterns
  - Guide: How to add new categories or adjust thresholds
- [ ] 16.5 Create troubleshooting guide
  - Common issues: AI analysis fails, scan doesn't detect tables, insights not showing
  - Solutions: Check config, verify AI API key, restart services
- [ ] 16.6 Update WORK_TRACKER.md
  - Move task from Active to Recently Completed
  - Add summary: What was built, key metrics (tables: 3, endpoints: 7, UI pages: 1)

---

## Parallel Execution Strategy

**Batch 1** (Launch simultaneously after Task 0):
- Agent 1: Tasks 1-2 (Database schema + config) - 2-3 hours
- Agent 2: Tasks 3-5 (Scanners: DB, Celery, API) - 3-4 hours
- Agent 3: Task 6 (Main scan script + Celery task) - 1-2 hours

**Batch 2** (After Batch 1 completes):
- Agent 4: Tasks 7-8 (AI analyzer + Celery task) - 3-4 hours
- Agent 5: Task 9 (API endpoints) - 2-3 hours

**Batch 3** (After Batch 2 completes):
- Agent 6: Tasks 10-11 (Frontend main + detail) - 3-4 hours
- Agent 7: Tasks 12-13 (Frontend insights + gaps tabs) - 2-3 hours

**Final** (Sequential):
- Agent 8: Tasks 14-16 (Testing + deployment + docs) - 3-4 hours

**Total with parallelization**: ~10-12 hours

---

## Verification

- [ ] Functional: All 3 phases working (scan, AI analysis, human review)
- [ ] Data: 30+ DB capabilities, 11+ Celery tasks, 10+ API endpoints discovered
- [ ] AI: Insights generated automatically, detects known bugs (Fear & Greed stale)
- [ ] UI: Can view capabilities, review insights, add notes
- [ ] Tests: 80%+ coverage, all passing (pytest + vitest)
- [ ] Quality: `~/portfolio-ai/scripts/lint.sh` passes (ruff + mypy --strict)
- [ ] Services: Restarted and verified (`bash ~/portfolio-ai/scripts/restart.sh`)
- [ ] Schedule: Daily scans run at 03:00 UTC, AI analysis at 03:15 UTC
- [ ] Integration: AI agents can query API before refactoring
- [ ] Docs: CLAUDE.md updated, user docs written

---

## Success Metrics

**Phase 1 (Auto-Discovery):**
- ✅ Discovered 30+ database tables with row counts, date ranges, field completeness
- ✅ Discovered 11+ Celery tasks with schedules, success rates
- ✅ Discovered 10+ API endpoints with dependencies
- ✅ Daily scans run automatically, update data

**Phase 2 (AI Analysis):**
- ✅ AI generates 15+ insights (5 critical, 10 high/medium)
- ✅ Detects actual bugs: Fear & Greed stale data, incomplete fields
- ✅ Suggests specific fixes with file paths
- ✅ Confidence scores >= 0.70

**Phase 3 (Human Review):**
- ✅ Can confirm/dismiss insights
- ✅ Can add strategic notes
- ✅ Notes persist across sessions
- ✅ AI agents reference notes during work

**End-to-End:**
- ✅ Market analyst scenario: Ask "what data is missing?", AI queries capabilities API, provides accurate gap analysis
- ✅ Refactoring scenario: Claude Code checks capabilities before changes, sees known issues, reads human notes, proceeds safely
