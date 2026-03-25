# Frontend Test Organization

Frontend automated tests in this repo use Vitest and React Testing Library.
Live page verification uses `sf-browser`, not Playwright.

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

Use the repo wrappers from the project root:

```bash
dt --frontend-only
dt --check
```

These tests should cover:

- component rendering and interaction
- API request/response shaping
- error and empty states
- regression coverage for fixed defects

## Browser Verification

For real browser checks, use `sf-browser` against the running app:

```bash
sf-browser health
sf-browser check http://<host-ip-from-.index.yaml>:3000/status /tmp/status-check.png
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
