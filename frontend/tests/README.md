# Frontend Test Organization

Frontend automated tests in this repo use Vitest and React Testing Library.
Live page verification uses `agent-browser`, not Playwright.

## Directory Structure

```text
frontend/tests/
├── fixtures/      # Shared mock data factories
├── setup.ts       # Vitest setup
└── README.md      # This file
```

Most tests are colocated with the source file they cover:

- `components/**/*.test.tsx`
- `lib/api/*.test.ts`
- `app/**/*.test.tsx`

## Automated Tests

Run from `~/portfolio-ai/frontend`:

```bash
npm test
npm run test:watch
npm run test:ui
npm run test:coverage
```

These tests should cover:

- component rendering and interaction
- API request/response shaping
- error and empty states
- regression coverage for fixed defects

## Browser Verification

For real browser checks, use `agent-browser` against the running app:

```bash
AGENT_BROWSER_SESSION=portfolio-ai ~/.local/bin/agent-browser open http://localhost:3000
```

Use it to verify:

- page load succeeds
- navigation works
- console stays clean
- visible controls behave correctly

## Shared Utilities

`fixtures/mockData.ts` provides reusable factories for frontend tests.

`setup.ts` loads:

- React Testing Library cleanup
- `jest-dom` matchers
- `matchMedia` mock
- `IntersectionObserver` mock

## Notes

- Prefer colocated regression tests over large framework-level harnesses.
- Keep docs aligned with current repo tooling.
- Do not reintroduce Playwright-based ad hoc verification for this project workflow.
