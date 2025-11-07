# Task List: Folder Structure Reorganization

**Type**: Standalone Task List
**Status**: Ready for Implementation
**Completion**: 0%
**Effort**: HIGH (~3-4 days)
**Created**: 2025-11-06
**Updated**: 2025-11-06

---

## Summary

Comprehensive reorganization of test structure and setup of frontend testing infrastructure based on industry best practices and 2025 patterns.

**✅ COMPLETE:** (None)
**🔄 IN PROGRESS:** (Not started)
**⚠️ NEXT:** Task 1.0

---

## Scope

### Priority 1: Backend Test Reorganization (~1 day)
- Reorganize 26 root-level test files into unit/ and integration/ directories
- Create clear categorization based on test type (unit vs integration)
- Add test organization documentation

### Priority 2: Frontend Test Setup (~2-3 days)
- Install and configure Vitest for component/hook testing
- Install and configure Playwright for E2E testing
- Create example tests demonstrating patterns
- Document frontend testing approach

### Priority 3: Cross-Stack Integration (Future - Document Only)
- Document structure for future cross-stack integration tests
- Update architecture documentation

### Documentation Updates
- Merge PROJECT_STRUCTURE.md into docs/core/DEVELOPMENT.md
- Update CLAUDE.md with test organization info
- Update docs/core/ARCHITECTURE.md with testing strategy
- Create comprehensive test documentation

---

## Relevant Files

### Create (12 files)
- `backend/tests/README.md` (~150 lines) - Backend test organization guide
- `backend/tests/fixtures/conftest.py` (~200 lines) - Moved from backend/tests/conftest.py
- `frontend/vitest.config.ts` (~30 lines) - Vitest configuration
- `frontend/tests/setup.ts` (~20 lines) - Test setup file
- `frontend/playwright.config.ts` (~40 lines) - Playwright configuration
- `frontend/tests/README.md` (~100 lines) - Frontend test guide
- `frontend/components/ui/button.test.tsx` (~30 lines) - Example component test
- `frontend/lib/api/watchlist.test.ts` (~50 lines) - Example API test
- `frontend/tests/e2e/watchlist.spec.ts` (~40 lines) - Example E2E test
- `docs/reference/testing-strategy.md` (~200 lines) - Comprehensive testing guide
- `docs/reference/cross-stack-testing.md` (~100 lines) - Future cross-stack test structure
- `scripts/test-all.sh` (~50 lines) - Run all tests (backend + frontend)

### Update (5 files)
- `docs/core/DEVELOPMENT.md` - Merge PROJECT_STRUCTURE.md content, add test organization
- `docs/core/ARCHITECTURE.md` - Add testing strategy section
- `CLAUDE.md` - Update with test organization quick reference
- `frontend/package.json` - Add test scripts and dependencies
- `tasks/WORK_TRACKER.md` - Add this task to Active Work

### Move/Reorganize (26 files)
- All root-level backend test files → unit/ or integration/ subdirectories
- `backend/tests/conftest.py` → `backend/tests/fixtures/conftest.py`

### Delete (1 file)
- `PROJECT_STRUCTURE.md` - Content merged into DEVELOPMENT.md

### Notes
- Backend tests: `cd ~/portfolio-ai/backend && pytest tests/ -v`
- Frontend tests: `cd ~/portfolio-ai/frontend && npm test`
- All tests: `bash ~/portfolio-ai/scripts/test-all.sh`
- Lint: `~/portfolio-ai/scripts/lint.sh`

---

## Tasks

### Phase 1: Backend Test Reorganization

- [ ] 1.0 **Analyze and categorize backend tests**
  - [ ] 1.0.1 Create categorization criteria document (2 min)
    - Define: Unit test = no DB, no HTTP, mocked dependencies
    - Define: Integration test = uses DB, HTTP, or external APIs
    - Document in backend/tests/README.md draft

  - [ ] 1.0.2 Audit each root-level test file (30 min)
    - Read imports and fixtures for each of 26 files
    - Categorize as UNIT or INTEGRATION
    - Create categorization mapping (test_name → category → target_dir)
    - Expected output: Markdown table with categorization

  - [ ] 1.0.3 Create new directory structure (2 min)
    ```bash
    mkdir -p ~/portfolio-ai/backend/tests/unit/{agents,analytics,portfolio,sources,storage,utils}
    mkdir -p ~/portfolio-ai/backend/tests/integration/{api,portfolio,sources,storage}
    mkdir -p ~/portfolio-ai/backend/tests/fixtures
    ```

- [ ] 1.1 **Move test files systematically (Group 1: Sources - 6 files)**
  - [ ] 1.1.1 Move test_alphavantage_source.py (2 min)
    - Categorize: UNIT (mocked HTTP responses)
    - `git mv ~/portfolio-ai/backend/tests/test_alphavantage_source.py ~/portfolio-ai/backend/tests/unit/sources/`

  - [ ] 1.1.2 Move test_finnhub_source.py (2 min)
    - Categorize: UNIT (mocked responses)
    - `git mv ~/portfolio-ai/backend/tests/test_finnhub_source.py ~/portfolio-ai/backend/tests/unit/sources/`

  - [ ] 1.1.3 Move test_fmp_source.py (2 min)
    - Categorize: UNIT (mocked responses)
    - `git mv ~/portfolio-ai/backend/tests/test_fmp_source.py ~/portfolio-ai/backend/tests/unit/sources/`

  - [ ] 1.1.4 Move test_twelvedata_source.py (2 min)
    - Categorize: UNIT (mocked responses)
    - `git mv ~/portfolio-ai/backend/tests/test_twelvedata_source.py ~/portfolio-ai/backend/tests/unit/sources/`

  - [ ] 1.1.5 Move test_yfinance_source.py (2 min)
    - Categorize: UNIT (mocked responses)
    - `git mv ~/portfolio-ai/backend/tests/test_yfinance_source.py ~/portfolio-ai/backend/tests/unit/sources/`

  - [ ] 1.1.6 Move test_multi_source.py (2 min)
    - Categorize: UNIT (tests source coordination)
    - `git mv ~/portfolio-ai/backend/tests/test_multi_source.py ~/portfolio-ai/backend/tests/unit/sources/`

- [ ] 1.2 **Move test files (Group 2: API Endpoints - 6 files)**
  - [ ] 1.2.1 Move test_api_analytics.py (2 min)
    - Categorize: INTEGRATION (uses DB, HTTP)
    - `git mv ~/portfolio-ai/backend/tests/test_api_analytics.py ~/portfolio-ai/backend/tests/integration/api/`

  - [ ] 1.2.2 Move test_api_ideas.py (2 min)
    - Categorize: INTEGRATION
    - `git mv ~/portfolio-ai/backend/tests/test_api_ideas.py ~/portfolio-ai/backend/tests/integration/api/`

  - [ ] 1.2.3 Move test_api_market.py (2 min)
    - Categorize: INTEGRATION
    - `git mv ~/portfolio-ai/backend/tests/test_api_market.py ~/portfolio-ai/backend/tests/integration/api/`

  - [ ] 1.2.4 Move test_api_portfolio.py (2 min)
    - Categorize: INTEGRATION
    - `git mv ~/portfolio-ai/backend/tests/test_api_portfolio.py ~/portfolio-ai/backend/tests/integration/api/`

  - [ ] 1.2.5 Move test_api_preferences.py (2 min)
    - Categorize: INTEGRATION
    - `git mv ~/portfolio-ai/backend/tests/test_api_preferences.py ~/portfolio-ai/backend/tests/integration/api/`

  - [ ] 1.2.6 Move test_api_watchlist.py (2 min)
    - Categorize: INTEGRATION
    - `git mv ~/portfolio-ai/backend/tests/test_api_watchlist.py ~/portfolio-ai/backend/tests/integration/api/`

- [ ] 1.3 **Move test files (Group 3: Portfolio Logic - 5 files)**
  - [ ] 1.3.1 Move test_portfolio_manager.py (2 min)
    - Categorize: UNIT (business logic)
    - `git mv ~/portfolio-ai/backend/tests/test_portfolio_manager.py ~/portfolio-ai/backend/tests/unit/portfolio/`

  - [ ] 1.3.2 Move test_portfolio_analytics.py (2 min)
    - Categorize: UNIT (calculation logic)
    - `git mv ~/portfolio-ai/backend/tests/test_portfolio_analytics.py ~/portfolio-ai/backend/tests/unit/portfolio/`

  - [ ] 1.3.3 Move test_portfolio_analyzer.py (2 min)
    - Categorize: UNIT (analysis logic)
    - `git mv ~/portfolio-ai/backend/tests/test_portfolio_analyzer.py ~/portfolio-ai/backend/tests/unit/portfolio/`

  - [ ] 1.3.4 Move test_integration_portfolio_crud.py (2 min)
    - Categorize: INTEGRATION (DB operations)
    - `git mv ~/portfolio-ai/backend/tests/test_integration_portfolio_crud.py ~/portfolio-ai/backend/tests/integration/portfolio/`

  - [ ] 1.3.5 Move test_price_fetcher.py (2 min)
    - Categorize: UNIT (coordination logic)
    - `git mv ~/portfolio-ai/backend/tests/test_price_fetcher.py ~/portfolio-ai/backend/tests/unit/sources/`

- [ ] 1.4 **Move test files (Group 4: Analytics & Utilities - 5 files)**
  - [ ] 1.4.1 Move test_indicators.py (2 min)
    - Categorize: UNIT (calculation logic)
    - `git mv ~/portfolio-ai/backend/tests/test_indicators.py ~/portfolio-ai/backend/tests/unit/analytics/`

  - [ ] 1.4.2 Move test_volume.py (2 min)
    - Categorize: UNIT (calculation logic)
    - `git mv ~/portfolio-ai/backend/tests/test_volume.py ~/portfolio-ai/backend/tests/unit/analytics/`

  - [ ] 1.4.3 Move test_sectors.py (2 min)
    - Categorize: UNIT (data processing)
    - `git mv ~/portfolio-ai/backend/tests/test_sectors.py ~/portfolio-ai/backend/tests/unit/analytics/`

  - [ ] 1.4.4 Move test_peers.py (2 min)
    - Categorize: UNIT (data processing)
    - `git mv ~/portfolio-ai/backend/tests/test_peers.py ~/portfolio-ai/backend/tests/unit/analytics/`

  - [ ] 1.4.5 Move test_jsonpath_mapper.py (2 min)
    - Categorize: UNIT (utility logic)
    - `git mv ~/portfolio-ai/backend/tests/test_jsonpath_mapper.py ~/portfolio-ai/backend/tests/unit/utils/`

- [ ] 1.5 **Move test files (Group 5: Agents & Storage - 4 files)**
  - [ ] 1.5.1 Move test_discovery_agent.py (2 min)
    - Categorize: UNIT (agent logic)
    - `git mv ~/portfolio-ai/backend/tests/test_discovery_agent.py ~/portfolio-ai/backend/tests/unit/agents/`

  - [ ] 1.5.2 Move test_agent_tools.py (2 min)
    - Categorize: UNIT (tool logic)
    - `git mv ~/portfolio-ai/backend/tests/test_agent_tools.py ~/portfolio-ai/backend/tests/unit/agents/`

  - [ ] 1.5.3 Move test_storage_schema.py (2 min)
    - Categorize: INTEGRATION (DB schema)
    - `git mv ~/portfolio-ai/backend/tests/test_storage_schema.py ~/portfolio-ai/backend/tests/integration/storage/`

  - [ ] 1.5.4 Move test_multi_source_price_fetcher.py (2 min)
    - Categorize: UNIT (coordination logic)
    - `git mv ~/portfolio-ai/backend/tests/test_multi_source_price_fetcher.py ~/portfolio-ai/backend/tests/unit/sources/`

- [ ] 1.6 **Move test files (Group 6: Logging & Config - 1 file)**
  - [ ] 1.6.1 Move test_logging_config.py (2 min)
    - Categorize: UNIT (config logic)
    - `git mv ~/portfolio-ai/backend/tests/test_logging_config.py ~/portfolio-ai/backend/tests/unit/utils/`

- [ ] 1.7 **Reorganize fixtures and conftest**
  - [ ] 1.7.1 Move conftest.py to fixtures/ (2 min)
    - `git mv ~/portfolio-ai/backend/tests/conftest.py ~/portfolio-ai/backend/tests/fixtures/conftest.py`

  - [ ] 1.7.2 Verify pytest discovery still works (2 min)
    - Run: `cd ~/portfolio-ai/backend && pytest tests/ --collect-only`
    - Verify: All tests discovered correctly
    - Fix: Update conftest.py imports if needed

- [ ] 1.8 **Verify all tests pass after reorganization**
  - [ ] 1.8.1 Run all backend tests (5 min)
    - `cd ~/portfolio-ai/backend && pytest tests/ -v`
    - Expected: All 377 tests pass

  - [ ] 1.8.2 Fix any import issues (10 min)
    - If tests fail, update relative imports
    - Common fix: Update conftest imports

  - [ ] 1.8.3 Run mypy type checking (3 min)
    - `cd ~/portfolio-ai/backend && mypy app/ --strict`
    - Verify: No new type errors

- [ ] 1.9 **Create backend test documentation**
  - [ ] 1.9.1 Write backend/tests/README.md (15 min)
    - Section: Structure overview (unit/ vs integration/)
    - Section: When to write unit tests
    - Section: When to write integration tests
    - Section: Running tests (pytest commands)
    - Section: Test fixtures and utilities
    - Section: Writing new tests (patterns and examples)

  - [ ] 1.9.2 Add __init__.py files to new directories (2 min)
    ```bash
    touch ~/portfolio-ai/backend/tests/unit/agents/__init__.py
    touch ~/portfolio-ai/backend/tests/unit/analytics/__init__.py
    touch ~/portfolio-ai/backend/tests/unit/portfolio/__init__.py
    touch ~/portfolio-ai/backend/tests/unit/sources/__init__.py
    touch ~/portfolio-ai/backend/tests/unit/storage/__init__.py
    touch ~/portfolio-ai/backend/tests/unit/utils/__init__.py
    touch ~/portfolio-ai/backend/tests/fixtures/__init__.py
    ```

### Phase 2: Frontend Test Infrastructure Setup

- [ ] 2.0 **Install frontend testing dependencies**
  - [ ] 2.0.1 Install Vitest and React Testing Library (3 min)
    ```bash
    cd ~/portfolio-ai/frontend
    npm install -D vitest @vitejs/plugin-react
    npm install -D @testing-library/react @testing-library/jest-dom @testing-library/user-event
    npm install -D jsdom
    ```

  - [ ] 2.0.2 Install Playwright for E2E testing (3 min)
    ```bash
    cd ~/portfolio-ai/frontend
    npm install -D @playwright/test
    npx playwright install chromium
    ```

  - [ ] 2.0.3 Install additional test utilities (2 min)
    ```bash
    npm install -D @vitest/ui
    npm install -D @vitest/coverage-v8
    ```

- [ ] 2.1 **Configure Vitest**
  - [ ] 2.1.1 Create vitest.config.ts (5 min)
    - Import: defineConfig from vitest, react plugin
    - Configure: jsdom environment, setup files
    - Configure: globals: true for describe/it/expect
    - Configure: path alias '@' → './'
    - Configure: coverage settings

  - [ ] 2.1.2 Create tests/setup.ts (3 min)
    - Import: @testing-library/jest-dom
    - Import: cleanup, afterEach from testing-library
    - Setup: Automatic cleanup after each test
    - Setup: Mock window.matchMedia (for responsive components)

  - [ ] 2.1.3 Update package.json with test scripts (3 min)
    ```json
    "scripts": {
      "test": "vitest",
      "test:ui": "vitest --ui",
      "test:coverage": "vitest --coverage",
      "test:watch": "vitest --watch"
    }
    ```

- [ ] 2.2 **Configure Playwright**
  - [ ] 2.2.1 Create playwright.config.ts (10 min)
    - Configure: testDir as './tests/e2e'
    - Configure: baseURL as 'http://192.168.8.233:3000'
    - Configure: fullyParallel: true
    - Configure: retries: 2 for CI, 0 for local
    - Configure: trace: 'on-first-retry'
    - Configure: webServer to auto-start dev server
    - Configure: projects for chromium only (can add more later)

  - [ ] 2.2.2 Create tests/e2e directory structure (2 min)
    ```bash
    mkdir -p ~/portfolio-ai/frontend/tests/e2e
    mkdir -p ~/portfolio-ai/frontend/tests/fixtures
    ```

  - [ ] 2.2.3 Update package.json with E2E scripts (2 min)
    ```json
    "scripts": {
      "test:e2e": "playwright test",
      "test:e2e:ui": "playwright test --ui",
      "test:e2e:debug": "playwright test --debug"
    }
    ```

- [ ] 2.3 **Create example component tests**
  - [ ] 2.3.1 Create button.test.tsx (10 min)
    - Location: `frontend/components/ui/button.test.tsx`
    - Test: Renders children text
    - Test: Handles click events
    - Test: Applies variant styles correctly
    - Test: Supports disabled state

  - [ ] 2.3.2 Create example API client test (10 min)
    - Location: `frontend/lib/api/watchlist.test.ts`
    - Mock: fetch API responses
    - Test: Fetches watchlist successfully
    - Test: Handles API errors gracefully
    - Test: Transforms response data correctly

  - [ ] 2.3.3 Create mock data utilities (10 min)
    - Location: `frontend/tests/fixtures/mockData.ts`
    - Export: mockWatchlistItem()
    - Export: mockPortfolioPosition()
    - Export: mockNewsArticle()
    - Export: mockIdea()

- [ ] 2.4 **Create example E2E tests**
  - [ ] 2.4.1 Create watchlist E2E test (15 min)
    - Location: `frontend/tests/e2e/watchlist.spec.ts`
    - Test: Page loads and displays table
    - Test: Columns are visible (Symbol, Signal, Price, etc.)
    - Test: Can expand row for details
    - Test: Signal badges display correctly

  - [ ] 2.4.2 Create portfolio E2E test (15 min)
    - Location: `frontend/tests/e2e/portfolio.spec.ts`
    - Test: Page loads and displays positions
    - Test: Can add new position
    - Test: Can edit existing position
    - Test: Analytics section updates

  - [ ] 2.4.3 Create navigation E2E test (10 min)
    - Location: `frontend/tests/e2e/navigation.spec.ts`
    - Test: Can navigate between all pages
    - Test: Active page highlighted in nav
    - Test: All pages load without errors

- [ ] 2.5 **Verify frontend tests work**
  - [ ] 2.5.1 Run Vitest tests (3 min)
    - `cd ~/portfolio-ai/frontend && npm test`
    - Expected: Example tests pass

  - [ ] 2.5.2 Run Playwright tests (5 min)
    - `cd ~/portfolio-ai/frontend && npm run test:e2e`
    - Expected: E2E tests pass
    - Note: Requires backend running

  - [ ] 2.5.3 Generate coverage report (3 min)
    - `cd ~/portfolio-ai/frontend && npm run test:coverage`
    - Review: Coverage report generated

- [ ] 2.6 **Create frontend test documentation**
  - [ ] 2.6.1 Write frontend/tests/README.md (20 min)
    - Section: Overview (Vitest + Playwright)
    - Section: Component testing with Vitest
    - Section: E2E testing with Playwright
    - Section: Running tests locally
    - Section: Writing new tests (patterns)
    - Section: Mock data and fixtures
    - Section: Debugging tests

  - [ ] 2.6.2 Add testing examples to each section (10 min)
    - Example: Component test pattern
    - Example: Hook test pattern
    - Example: API client test pattern
    - Example: E2E test pattern

### Phase 3: Cross-Stack Integration Tests (Document Only)

- [ ] 3.0 **Document future cross-stack test structure**
  - [ ] 3.0.1 Create docs/reference/cross-stack-testing.md (15 min)
    - Section: Purpose (tests spanning frontend + backend)
    - Section: Proposed structure (top-level tests/ directory)
    - Section: When to use cross-stack tests
    - Section: API contract testing approach
    - Section: End-to-end workflow testing approach

  - [ ] 3.0.2 Add placeholder structure documentation (5 min)
    ```markdown
    ## Proposed Structure

    portfolio-ai/
    ├── tests/
    │   ├── integration/
    │   │   ├── api-contract/
    │   │   ├── watchlist-refresh/
    │   │   └── portfolio-sync/
    │   ├── fixtures/
    │   │   ├── seed-data.sql
    │   │   └── mock-responses.json
    │   └── README.md
    ```

  - [ ] 3.0.3 Document when to implement (2 min)
    - Criteria: After frontend has established test patterns
    - Criteria: When need for cross-stack contract tests emerges
    - Criteria: When E2E workflow tests become valuable

### Phase 4: Documentation Updates

- [ ] 4.0 **Merge PROJECT_STRUCTURE.md into DEVELOPMENT.md**
  - [ ] 4.0.1 Read both files completely (5 min)
    - Read: docs/core/DEVELOPMENT.md
    - Read: PROJECT_STRUCTURE.md
    - Identify: Overlapping content
    - Identify: Unique content in PROJECT_STRUCTURE.md

  - [ ] 4.0.2 Add "Directory Structure" section to DEVELOPMENT.md (10 min)
    - Location: After "Overview" section
    - Content: Key directory paths from PROJECT_STRUCTURE.md
    - Content: Virtual environment location and importance
    - Content: Test file locations
    - Content: Common path confusion warnings

  - [ ] 4.0.3 Add "Path Conventions" section to DEVELOPMENT.md (5 min)
    - Content: Always use absolute paths in scripts
    - Content: cd into backend/ before running Python tools
    - Content: Path examples and anti-patterns

  - [ ] 4.0.4 Delete PROJECT_STRUCTURE.md (2 min)
    - `git rm ~/portfolio-ai/PROJECT_STRUCTURE.md`

  - [ ] 4.0.5 Update references to PROJECT_STRUCTURE.md (5 min)
    - Search: `grep -r "PROJECT_STRUCTURE.md" ~/portfolio-ai/`
    - Update: Change references to DEVELOPMENT.md
    - Files likely: CLAUDE.md, README.md

- [ ] 4.1 **Update CLAUDE.md with test organization**
  - [ ] 4.1.1 Add "Test Organization" quick reference section (10 min)
    - Location: After "Database Quick Reference"
    - Content: Backend test structure (unit/ vs integration/)
    - Content: Frontend test structure (Vitest + Playwright)
    - Content: Running all tests

  - [ ] 4.1.2 Update quick start commands (3 min)
    - Add: Test commands to development cycle
    - Add: `npm test` for frontend
    - Add: `pytest tests/` for backend

- [ ] 4.2 **Update ARCHITECTURE.md with testing strategy**
  - [ ] 4.2.1 Add "Testing Strategy" section (15 min)
    - Location: After "Development Philosophy"
    - Subsection: Test organization principles
    - Subsection: Backend testing approach (unit vs integration)
    - Subsection: Frontend testing approach (Vitest + Playwright)
    - Subsection: Future cross-stack testing

  - [ ] 4.2.2 Add testing pyramid diagram (5 min)
    ```
    Backend:
    - Unit Tests (fast, many) - unit/
    - Integration Tests (realistic, fewer) - integration/

    Frontend:
    - Component Tests (fast, many) - Vitest
    - E2E Tests (slow, critical paths) - Playwright

    Cross-Stack (future):
    - API Contract Tests
    - Workflow Tests
    ```

- [ ] 4.3 **Create comprehensive testing guide**
  - [ ] 4.3.1 Create docs/reference/testing-strategy.md (30 min)
    - Section: Overview of testing philosophy
    - Section: Backend testing guide (detailed)
    - Section: Frontend testing guide (detailed)
    - Section: Cross-stack testing (future)
    - Section: Test data and fixtures
    - Section: CI/CD integration (future)
    - Section: Best practices and patterns
    - Section: Troubleshooting common issues

- [ ] 4.4 **Create unified test runner script**
  - [ ] 4.4.1 Create scripts/test-all.sh (10 min)
    ```bash
    #!/bin/bash
    # Run all tests (backend + frontend)

    echo "=== Running Backend Tests ==="
    cd ~/portfolio-ai/backend
    source .venv/bin/activate
    pytest tests/ -v
    BACKEND_EXIT=$?

    echo ""
    echo "=== Running Frontend Tests ==="
    cd ~/portfolio-ai/frontend
    npm test
    FRONTEND_EXIT=$?

    # Summary
    if [ $BACKEND_EXIT -eq 0 ] && [ $FRONTEND_EXIT -eq 0 ]; then
      echo "✅ All tests passed"
      exit 0
    else
      echo "❌ Some tests failed"
      exit 1
    fi
    ```

  - [ ] 4.4.2 Make script executable (1 min)
    - `chmod +x ~/portfolio-ai/scripts/test-all.sh`

  - [ ] 4.4.3 Test the script (3 min)
    - `bash ~/portfolio-ai/scripts/test-all.sh`
    - Verify: Runs both test suites
    - Verify: Reports success/failure correctly

### Phase 5: Final Verification

- [ ] 5.0 **Run complete test suite**
  - [ ] 5.0.1 Run backend tests (5 min)
    - `cd ~/portfolio-ai/backend && pytest tests/ -v`
    - Expected: All 377 tests pass

  - [ ] 5.0.2 Run frontend tests (3 min)
    - `cd ~/portfolio-ai/frontend && npm test`
    - Expected: All example tests pass

  - [ ] 5.0.3 Run E2E tests (5 min)
    - Start services: `bash ~/portfolio-ai/scripts/start.sh`
    - Run: `cd ~/portfolio-ai/frontend && npm run test:e2e`
    - Expected: E2E tests pass

  - [ ] 5.0.4 Run unified test script (5 min)
    - `bash ~/portfolio-ai/scripts/test-all.sh`
    - Expected: Both suites pass

- [ ] 5.1 **Run quality checks**
  - [ ] 5.1.1 Run linting (3 min)
    - `bash ~/portfolio-ai/scripts/lint.sh`
    - Expected: All checks pass

  - [ ] 5.1.2 Run mypy (3 min)
    - `cd ~/portfolio-ai/backend && mypy app/ --strict`
    - Expected: No type errors

  - [ ] 5.1.3 Verify file sizes (2 min)
    - `bash ~/portfolio-ai/scripts/check-file-sizes.sh`
    - Expected: All files within guidelines

- [ ] 5.2 **Update WORK_TRACKER.md**
  - [ ] 5.2.1 Move task to "Recently Completed" (2 min)
    - Add completion date
    - Add summary of changes
    - Mark as 100% complete

- [ ] 5.3 **Create summary of changes**
  - [ ] 5.3.1 Document what was reorganized (5 min)
    - Count: Files moved (26 backend test files)
    - Count: New directories created
    - Count: New files created (frontend tests)

  - [ ] 5.3.2 Create before/after directory tree comparison (5 min)
    - Show: Old structure (flat)
    - Show: New structure (organized)
    - Highlight: Key improvements

---

## Verification (MANDATORY before "COMPLETE ✅")

- [ ] **Functional**: All tests organized and passing
  - [ ] Backend: All 377 tests pass in new structure
  - [ ] Frontend: Example tests demonstrate patterns
  - [ ] E2E: Playwright tests run successfully
  - [ ] Unified: test-all.sh script works correctly

- [ ] **Tests**: New test infrastructure validated
  - [ ] Backend: pytest discovery works in new structure
  - [ ] Frontend: Vitest discovers and runs component tests
  - [ ] Frontend: Playwright discovers and runs E2E tests
  - [ ] Coverage: Coverage reporting works for both stacks

- [ ] **Quality**: All checks pass
  - [ ] Linting: scripts/lint.sh passes
  - [ ] Types: mypy --strict passes
  - [ ] Files: All within size guidelines
  - [ ] Imports: All test imports work correctly

- [ ] **Clean**: Code quality maintained
  - [ ] No duplicate test fixtures
  - [ ] Clear categorization (unit vs integration)
  - [ ] Consistent naming patterns
  - [ ] Well-documented patterns

- [ ] **Docs**: Comprehensive documentation
  - [ ] backend/tests/README.md complete
  - [ ] frontend/tests/README.md complete
  - [ ] docs/reference/testing-strategy.md complete
  - [ ] ARCHITECTURE.md updated with testing strategy
  - [ ] DEVELOPMENT.md includes PROJECT_STRUCTURE content
  - [ ] CLAUDE.md updated with quick reference

- [ ] **Ops**: Developer experience improved
  - [ ] Easy to find tests for any module
  - [ ] Clear patterns for writing new tests
  - [ ] Unified test runner script works
  - [ ] Documentation is discoverable

---

## Notes

### Test Categorization Guidelines

**Unit Test Characteristics**:
- No database connections
- No HTTP requests to external APIs
- All external dependencies mocked
- Fast execution (< 100ms per test)
- Tests single function/class in isolation

**Integration Test Characteristics**:
- Uses test database (portfolio_ai_test)
- Makes HTTP requests (real or test server)
- Calls external APIs (with mocking for reliability)
- Slower execution (< 5s per test)
- Tests interaction between components

### Frontend Testing Approach

**Vitest (Component/Hook Testing)**:
- Fast unit tests for UI components
- Tests component behavior, not implementation
- Uses React Testing Library patterns
- Runs in jsdom environment

**Playwright (E2E Testing)**:
- Real browser automation
- Tests complete user workflows
- Validates full stack integration
- Runs against actual dev server

### Migration Safety

All file moves use `git mv` to preserve history. If issues arise:
1. Check `git status` to see moves
2. Rollback with `git reset --hard` if needed
3. Tests verify nothing broke after moves

### Context Management

This is a HIGH effort task (~3-4 days). Monitor context usage:
- Current budget: 200K tokens
- Pause at: 170-180K tokens (85-90%)
- Use: `/pause_it` if context limits reached
- Resume: Task list tracks progress for resuming
