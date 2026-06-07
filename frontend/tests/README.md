# Frontend tests

Frontend automated tests use Vitest and React Testing Library.

## Directory structure

```text
frontend/tests/
├── fixtures/      # Shared mock data factories
├── setup.ts       # Vitest setup
└── README.md      # This file
```

Most tests are colocated with the source they cover:

- `components/**/*.test.tsx`
- `lib/api/*.test.ts`
- `app/**/*.test.tsx`

## Commands

```bash
pnpm lint
pnpm exec tsc --noEmit
pnpm test -- --run
pnpm build
```

Use a real browser against a running local app for manual smoke checks:

```bash
curl -fsS http://localhost:3000 >/dev/null
```

Also inspect the browser console before trusting UI changes.

## Shared utilities

`fixtures/mockData.ts` provides reusable factories. `setup.ts` loads React Testing Library cleanup, `jest-dom` matchers, `matchMedia`, and `IntersectionObserver` mocks.
