# Frontend notes

The frontend is a Next.js App Router application served on port `3000`.

## Local development

```bash
pnpm install --frozen-lockfile
pnpm build
API_URL=http://localhost:8000 HOSTNAME=0.0.0.0 PORT=3000 pnpm start
```

The browser uses same-origin `/api/*` and `/ws/*` routing. Next.js route handlers proxy `/api/*` at runtime, and the WebSocket rewrite proxies `/ws/*` to `API_URL`. This keeps native and Docker installs aligned without exposing a browser-side backend port setting.

`pnpm start` stages `.next/static` and `public/` into the standalone runtime directory before launching `server.js`, matching the Docker image layout.

## Quality checks

```bash
pnpm lint
pnpm exec tsc --noEmit
pnpm test -- --run
pnpm build
```

## API routing

- Browser traffic stays same-origin on `/api/*` and `/ws/*`.
- App Router route handlers proxy `/api/*` and `/health/*` to `API_URL` at runtime.
- A Next.js rewrite proxies `/ws/*` to `API_URL`.
- Server-side rendering also uses `API_URL`.
- Production starts should use `pnpm start`, which stages standalone assets and runs `node server.js` from `.next/standalone`.

## Watchlist selective update animations

The desktop watchlist table exposes lightweight data attributes so `app/globals-watchlist.css` can animate only the cells and rows that changed:

- Each table row carries `data-slot="table-row"` and toggles `data-recently-updated="true"` for about one second after a snapshot delta is detected.
- Every cell exposes `data-slot="table-cell"`; changed values set `data-changed="true"` for about two seconds.
- Price labels and score badges use dedicated classes (`price-display`, `score-badge`) for focus and transition rules.

When adding columns, reuse the same pattern so change detection and scoped animations stay consistent.
