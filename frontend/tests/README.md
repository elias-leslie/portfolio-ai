# Frontend Test Organization

This directory contains all frontend tests for the Portfolio AI platform, organized by test type.

---

## 📁 Directory Structure

```
frontend/tests/
├── e2e/                   # End-to-end tests (Playwright)
│   ├── watchlist.spec.ts  # Watchlist page E2E tests
│   ├── portfolio.spec.ts  # Portfolio page E2E tests
│   └── navigation.spec.ts # Navigation and routing tests
├── fixtures/              # Shared test utilities
│   └── mockData.ts        # Mock data factories
├── setup.ts               # Vitest test setup
└── README.md              # This file
```

**Component tests** are co-located with their source files:
- `components/ui/button.test.tsx` - Tests for Button component
- `lib/api/watchlist.test.ts` - Tests for watchlist API client (example)

---

## 🧪 Test Categories

### Component Tests (Vitest + React Testing Library)

**Location:** Alongside component files (`*.test.tsx`)

**Purpose:** Test React components in isolation

**Characteristics:**
- **Fast execution** (< 100ms per test)
- **Tests behavior, not implementation**
- **Uses jsdom environment** (simulated browser)
- **Isolated from backend** (mocked API calls)

**When to write a component test:**
- Testing UI component rendering
- Testing user interactions (clicks, typing, etc.)
- Testing component state changes
- Testing conditional rendering
- Testing accessibility features

**Example:**
```typescript
// components/ui/button.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { Button } from './button'

describe('Button', () => {
  it('handles click events', async () => {
    const handleClick = vi.fn()
    const user = userEvent.setup()

    render(<Button onClick={handleClick}>Click me</Button>)

    await user.click(screen.getByText('Click me'))

    expect(handleClick).toHaveBeenCalledOnce()
  })
})
```

### API Client Tests (Vitest)

**Location:** Alongside API client files (`*.test.ts`)

**Purpose:** Test API client logic and error handling

**Characteristics:**
- **Fast execution**
- **Mocked fetch/HTTP responses**
- **Tests request/response transformation**
- **Tests error handling**

**Example:**
```typescript
// lib/api/watchlist.test.ts
import { describe, it, expect, vi } from 'vitest'
import { mockWatchlistItem, mockApiResponse } from '@/tests/fixtures/mockData'

describe('Watchlist API', () => {
  it('fetches watchlist successfully', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      mockApiResponse({ items: [mockWatchlistItem()] })
    )

    const result = await fetchWatchlist()

    expect(result.items).toHaveLength(1)
    expect(result.items[0].symbol).toBe('AAPL')
  })
})
```

### End-to-End Tests (Playwright)

**Location:** `tests/e2e/*.spec.ts`

**Purpose:** Test complete user workflows in real browser

**Characteristics:**
- **Real browser automation** (Chromium)
- **Tests full stack integration** (frontend + backend)
- **Slower execution** (seconds per test)
- **Validates actual user experience**

**When to write an E2E test:**
- Testing critical user workflows (login, checkout, etc.)
- Testing page navigation
- Testing form submissions
- Testing real API integration
- Validating responsive design

**Example:**
```typescript
// tests/e2e/watchlist.spec.ts
import { test, expect } from '@playwright/test'

test('displays watchlist data', async ({ page }) => {
  await page.goto('/watchlist')

  await expect(page.locator('table')).toBeVisible()
  await expect(page.getByText('Symbol')).toBeVisible()
})
```

---

## 🚀 Running Tests

### Component/Unit Tests (Vitest)

```bash
cd ~/portfolio-ai/frontend

# Run all component tests
npm test

# Run in watch mode
npm run test:watch

# Run with UI
npm run test:ui

# Run with coverage
npm run test:coverage
```

### End-to-End Tests (Playwright)

```bash
cd ~/portfolio-ai/frontend

# Run all E2E tests (requires backend running)
npm run test:e2e

# Run with UI (visual test runner)
npm run test:e2e:ui

# Run in debug mode
npm run test:e2e:debug

# Run specific test file
npx playwright test tests/e2e/watchlist.spec.ts
```

### Run Specific Tests

```bash
# Run specific component test
npm test -- button.test.tsx

# Run tests matching pattern
npm test -- watchlist

# Run single E2E test
npx playwright test -g "displays watchlist data"
```

---

## 🔧 Test Utilities

### Mock Data Factories (`fixtures/mockData.ts`)

Pre-built factories for creating test data:

```typescript
import {
  mockWatchlistItem,
  mockPortfolioPosition,
  mockNewsArticle,
  mockIdea,
} from '@/tests/fixtures/mockData'

// Create mock data with defaults
const item = mockWatchlistItem()

// Override specific fields
const customItem = mockWatchlistItem({
  symbol: 'GOOGL',
  score: { overall: 90.0, ...
},
  })
```

### Test Setup (`setup.ts`)

**Automatic setup for all Vitest tests:**
- ✅ React Testing Library auto-cleanup
- ✅ jest-dom matchers (toBeInTheDocument, etc.)
- ✅ window.matchMedia mock (for responsive components)
- ✅ IntersectionObserver mock (for lazy loading)

---

## ✍️ Writing New Tests

### Component Test Pattern

```typescript
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import { MyComponent } from './MyComponent'

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent title="Test" />)

    expect(screen.getByText('Test')).toBeInTheDocument()
  })

  it('handles user interaction', async () => {
    const handleClick = vi.fn()
    const user = userEvent.setup()

    render(<MyComponent onClick={handleClick} />)

    await user.click(screen.getByRole('button'))

    expect(handleClick).toHaveBeenCalled()
  })
})
```

### E2E Test Pattern

```typescript
import { test, expect } from '@playwright/test'

test.describe('Feature Name', () => {
  test('user can complete workflow', async ({ page }) => {
    // Navigate to page
    await page.goto('/feature')

    // Interact with page
    await page.getByRole('button', { name: 'Submit' }).click()

    // Verify result
    await expect(page.getByText('Success')).toBeVisible()
  })
})
```

---

## 🐛 Debugging Tests

### Component Tests

```bash
# Run with verbose output
npm test -- -v

# Run specific test
npm test -- button.test.tsx -t "handles click events"

# Update snapshots (if using snapshots)
npm test -- -u
```

### E2E Tests

```bash
# Debug mode (step through tests)
npm run test:e2e:debug

# UI mode (visual test runner)
npm run test:e2e:ui

# Headed mode (see browser)
npx playwright test --headed

# Trace viewer (after test failure)
npx playwright show-trace trace.zip
```

---

## 📊 Test Coverage

**Target:** 80%+ coverage for critical paths

**View coverage report:**
```bash
npm run test:coverage
open coverage/index.html
```

**Coverage exclusions** (see `vitest.config.ts`):
- node_modules/
- tests/
- Type definition files (*.d.ts)
- Config files (*.config.*)
- Mock data files

---

## 🔍 Troubleshooting

### Vitest Issues

**"Cannot find module"**
- Solution: Check `vitest.config.ts` path alias configuration
- Verify imports use `@/` prefix

**"jsdom not defined"**
- Solution: Already configured in `vitest.config.ts`
- Verify `test.environment = 'jsdom'`

**"jest-dom matchers not working"**
- Solution: Import in test file: `import '@testing-library/jest-dom'`
- Or verify `setup.ts` is loaded

### Playwright Issues

**"Browser not installed"**
- Solution: Run `npx playwright install chromium`

**"Backend not running"**
- Solution: Start backend services first
- Playwright config auto-starts frontend (`npm run dev`)
- Backend must be started manually

**"Tests timeout"**
- Solution: Increase timeout in test: `{ timeout: 30000 }`
- Or globally in `playwright.config.ts`

---

## 📚 Testing Best Practices

### Component Tests

✅ **DO:**
- Test user-visible behavior
- Test accessibility (roles, labels)
- Use `getByRole` over `getByTestId`
- Mock API calls
- Test edge cases and errors

❌ **DON'T:**
- Test implementation details
- Test library code (React, Radix UI)
- Access component internals
- Test CSS (unless critical to behavior)

### E2E Tests

✅ **DO:**
- Test critical user workflows
- Test real API integration
- Verify page navigation
- Test responsive design
- Wait for network idle

❌ **DON'T:**
- Test unit logic (use component tests)
- Test every edge case (slow)
- Hardcode waits (`page.waitForTimeout`)
- Test what component tests cover

---

## 📖 Additional Resources

- **Testing Guide:** `docs/reference/testing-strategy.md`
- **Vitest Documentation:** https://vitest.dev/
- **React Testing Library:** https://testing-library.com/react
- **Playwright Documentation:** https://playwright.dev/
- **Testing Library Queries:** https://testing-library.com/docs/queries/about

---

**Last Updated:** 2025-11-06
**Test Framework:** Vitest 4.0.7 + Playwright 1.56.1
**Component Tests:** 8 passing
**E2E Tests:** 3 example tests created
