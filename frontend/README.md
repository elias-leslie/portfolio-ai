## Frontend Notes

Portfolio-AI's frontend is a Next.js App Router application served on port `3000`.

### Local development

```bash
pnpm install
pnpm dev
```

### Production-style rebuild

Use the shared rebuild wrapper:

```bash
rebuild.sh portfolio-ai
```

That rebuilds the frontend, applies backend migrations, and restarts the frontend/backend/worker services together.

### API routing

- Local development on `localhost` calls the backend directly at `http://localhost:8000`
- Any non-local browser host stays same-origin on `/api/*` and `/ws/*` so Next.js rewrites can proxy to the backend safely
- Cloudflare Access handles perimeter auth, so the frontend client stays same-origin and auth-agnostic

## Watchlist Selective Update Animations

The desktop watchlist table exposes lightweight data attributes so that `app/globals-watchlist.css` can animate only the cells and rows that changed:

- Each table row carries `data-slot="table-row"` and toggles `data-recently-updated="true"` for ~1s after a snapshot delta is detected. The root watchlist page sets `class="watchlist-page"` so these effects stay scoped to watchlist surfaces.
- Every cell exposes `data-slot="table-cell"`. When the backing value (price, overall score, signal, style, risk, timestamp) changes, the component sets `data-changed="true"` for ~2s which triggers the flash animation.
- Price labels and score badges also have dedicated classes (`price-display`, `score-badge`) to pick up the focus/transition rules defined in `globals-watchlist.css`.

When adding new columns, reuse the same pattern so that change detection and scoped animations continue to work consistently in both light and dark themes.

## Expandable Cards & Settings Sections

- Default behavior collapses the content; set `defaultCollapsed={false}` only for very small blocks (e.g., Profiles) where showing controls inline is more usable.
- When introducing a new status card or settings section, import these helpers instead of rolling your own collapse logic. This keeps interaction affordances (summary text, chevron button, focus handling) consistent and easier to maintain.
