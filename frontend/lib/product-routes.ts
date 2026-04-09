export type MainRoute = {
  href: '/' | '/portfolio' | '/money' | '/status'
  label: string
  description: string
  matchPrefixes?: string[]
}

export const PRIMARY_PRODUCT_ROUTES: MainRoute[] = [
  {
    href: '/',
    label: 'Today',
    description:
      'The single ranked queue for what matters now across money and investing.',
  },
  {
    href: '/portfolio',
    label: 'Investing',
    description:
      'Track symbols, holdings, and portfolio decisions in one workspace.',
    matchPrefixes: ['/portfolio', '/watchlist', '/symbols'],
  },
  {
    href: '/money',
    label: 'Money',
    description:
      'Keep household accounts current, surface data gaps, and add evidence.',
  },
]

export const SECONDARY_PRODUCT_ROUTES: MainRoute[] = [
  {
    href: '/status',
    label: 'Status',
    description: 'Check operations, freshness, and upstream system posture.',
  },
]

export function resolveMainProductRoute(pathname: string): MainRoute {
  return (
    PRIMARY_PRODUCT_ROUTES.find((route) =>
      (route.matchPrefixes ?? [route.href]).some((prefix) =>
        prefix === '/'
          ? pathname === '/'
          : pathname === prefix || pathname.startsWith(`${prefix}/`),
      ),
    ) ?? PRIMARY_PRODUCT_ROUTES[0]
  )
}

export function resolveSecondaryProductRoute(pathname: string): MainRoute | null {
  return (
    SECONDARY_PRODUCT_ROUTES.find((route) =>
      (route.matchPrefixes ?? [route.href]).some((prefix) =>
        prefix === '/'
          ? pathname === '/'
          : pathname === prefix || pathname.startsWith(`${prefix}/`),
      ),
    ) ?? null
  )
}
