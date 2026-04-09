export type MainRoute = {
  href: '/' | '/watchlist' | '/portfolio' | '/money' | '/status'
  label: string
  description: string
  matchPrefixes?: string[]
}

export const MAIN_PRODUCT_ROUTES: MainRoute[] = [
  {
    href: '/',
    label: 'Today',
    description:
      'Start with the highest-priority actions, ideas, and market context.',
  },
  {
    href: '/watchlist',
    label: 'Watchlist',
    description:
      'Track setups, score health, and symbol-specific follow-up work.',
    matchPrefixes: ['/watchlist', '/symbols'],
  },
  {
    href: '/portfolio',
    label: 'Portfolio Coach',
    description: 'Review concentration, sizing discipline, and live holdings.',
  },
  {
    href: '/money',
    label: 'Money System',
    description: 'Handle household questions, intake, reports, and planning.',
  },
  {
    href: '/status',
    label: 'Status',
    description: 'Check operations, freshness, and upstream system posture.',
  },
]

export function resolveMainProductRoute(pathname: string): MainRoute {
  return (
    MAIN_PRODUCT_ROUTES.find((route) =>
      (route.matchPrefixes ?? [route.href]).some((prefix) =>
        prefix === '/'
          ? pathname === '/'
          : pathname === prefix || pathname.startsWith(`${prefix}/`),
      ),
    ) ?? MAIN_PRODUCT_ROUTES[0]
  )
}
