# Portfolio AI Frontend Design Tokens

The frontend uses a dark-first, token-driven theme. All components must consume these tokens instead of hard-coded values or default Tailwind palettes. This document captures how to work with the system.

## Theme Overview

- **Dark by default** with `.light` overrides available.
- **CSS variables** are declared in `app/globals.css`; Tailwind aliases map to those variables through the config.
- **Tokens are semantic**: use the role that matches intent (surface, border, text, gain/loss, viz ramp, focus ring, motion).
- **ThemeProvider** (`components/providers/ThemeProvider.tsx`) handles system preference detection, persistence, and reduced-motion data attributes.

## Core Token Families

| Category | Description | Examples |
|----------|-------------|----------|
| Surfaces | Background layers for layouts/cards/dialogs | `bg-bg`, `bg-surface`, `bg-surface-elev`, `bg-surface-overlay` |
| Text & Accent | Foreground roles and highlights | `text-text`, `text-text-muted`, `text-primary`, `text-accent` |
| Borders & Shadows | Outline + elevation tokens | `border-border`, `border-border-subtle`, `shadow-sm`, `shadow-lg` |
| State | Focus/hover/disabled semantics | `focus-visible:ring-focus`, `hover:bg-surface-muted`, `disabled:opacity-40` |
| Financial | Gain/loss semantics | `text-gain`, `text-loss`, `bg-gain/15`, `bg-loss/15` |
| Data Viz | Sequential ramp for charts | `bg-viz-0` through `bg-viz-5`, or use CSS vars via `var(--color-chart-1)` |
| Motion | Transition durations/easing | `duration-200`, `duration-300`, `ease-linear` (mapped in Tailwind config) |

## Implementation Checklist

1. **Wrap pages with Providers**
   Ensure any new layout or route renders within `<Providers>` so theme context, reduced-motion data attributes, and React Query are available.

2. **Use token utilities**
   - Replace Tailwind defaults (`text-gray-500`, `bg-slate-900`) with semantic equivalents.
   - When tokens are missing, extend the Tailwind theme instead of using raw colors.

3. **Respect reduced-motion**
   - Read `prefersReducedMotion` from `useTheme()`.
   - Swap complex animations for opacity/fade transitions or disable them when true.

4. **Financial + status indicators**
   - Positive deltas → `text-gain` / `bg-gain/15`.
   - Negative deltas → `text-loss` / `bg-loss/15`.
   - Neutral states → `text-text-muted` or `bg-surface-muted`.
   - Pair color with iconography or labels to avoid color-only communication.

5. **Charts & Sparklines**
   - Use the `viz` ramps for line/area bar colors.
   - Chart backgrounds and gridlines should derive from `surface`/`border-subtle`.
   - Tooltips must use `bg-surface-overlay` and `text-text`.
   - Honor reduced motion by disabling continuous animations when `prefersReducedMotion` is `true`.

6. **Custom CSS**
   - Reference tokens via CSS variables: `var(--color-text)`, `var(--color-border)`, etc.
   - Prefer `color-mix` with existing tokens instead of introducing new color values.

7. **Testing**
   - Run `npm run lint`; ESLint enforces the color-token rule.
   - Manually verify both dark (default) and light themes by toggling the `ThemeToggle`.
   - Use the browser’s reduced-motion setting to confirm transitions respect preferences.

## Adding New Tokens

1. Extend `app/globals.css` with the new base token (both dark + `.light`).
2. Map the variable through Tailwind (colors, spacing, typography) if utility classes are required.
3. Document usage here so the team understands when to apply the new role.

## FAQ

- **Can I use Tailwind’s default palette?**
  No. If a utility isn’t mapped to the token system, add a mapping first.

- **How do I access the current theme programmatically?**
  Use the `useTheme()` hook; it provides `theme`, `resolvedTheme`, `prefersReducedMotion`, and `setTheme`.

- **Do I need to handle server-rendered theme mismatch?**
  No. `app/layout.tsx` injects an inline script that sets the class and data attributes before hydration.

Refer back to this guide whenever building new frontend surfaces or reviewing PRs for token compliance.
