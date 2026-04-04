## Frontend Notes

Portfolio-AI's frontend is a Next.js App Router application served on port `3000`.

### Local development

```bash
pnpm install --frozen-lockfile
pnpm build
API_URL=http://localhost:8000 HOSTNAME=0.0.0.0 PORT=3000 pnpm start
```

The browser always uses same-origin `/api/*` and `/ws/*` routing. Next.js
route handlers proxy `/api/*` at runtime and the WebSocket rewrite proxies
`/ws/*` to `API_URL`, which keeps native and Docker installs aligned without
requiring browser-side backend port knowledge.

`pnpm start` stages `.next/static` and `public/` into the standalone runtime
directory before launching `server.js`, which keeps native starts aligned with
the Docker image layout.

### SummitFlow runtime

The shared internal workspace still uses the wrapper-managed rebuild flow:

```bash
pnpm install
rebuild.sh portfolio-ai
status.sh portfolio-ai
```

Use `rebuild.sh portfolio-ai` only when you are inside the existing SummitFlow
runtime and intentionally relying on the shared wrapper-managed services.

### Production-style rebuild

For standalone release validation, prefer the root-level Docker compose stack or
the native instructions in the root `README.md`.

### API routing

- Browser traffic stays same-origin on `/api/*` and `/ws/*`
- App Router route handlers proxy `/api/*` and `/health/*` to `API_URL` at runtime
- A Next.js rewrite proxies `/ws/*` to `API_URL`
- Server-side rendering also uses `API_URL`
- Production starts should use `pnpm start`, which stages standalone assets and runs `node server.js` from `.next/standalone`

## Watchlist Selective Update Animations

The desktop watchlist table exposes lightweight data attributes so that `app/globals-watchlist.css` can animate only the cells and rows that changed:

- Each table row carries `data-slot="table-row"` and toggles `data-recently-updated="true"` for ~1s after a snapshot delta is detected. The root watchlist page sets `class="watchlist-page"` so these effects stay scoped to watchlist surfaces.
- Every cell exposes `data-slot="table-cell"`. When the backing value (price, overall score, signal, style, risk, timestamp) changes, the component sets `data-changed="true"` for ~2s which triggers the flash animation.
- Price labels and score badges also have dedicated classes (`price-display`, `score-badge`) to pick up the focus/transition rules defined in `globals-watchlist.css`.

When adding new columns, reuse the same pattern so that change detection and scoped animations continue to work consistently in both light and dark themes.

## Expandable Cards & Settings Sections

- Default behavior collapses the content; set `defaultCollapsed={false}` only for very small blocks (e.g., Profiles) where showing controls inline is more usable.
- When introducing a new status card or settings section, import these helpers instead of rolling your own collapse logic. This keeps interaction affordances (summary text, chevron button, focus handling) consistent and easier to maintain.
