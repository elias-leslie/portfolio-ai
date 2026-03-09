export type MainRoute = {
  href: '/' | '/watchlist' | '/portfolio' | '/money'
  label: string
}

export const ADVANCED_PRODUCT_MODE_ENABLED =
  process.env.NEXT_PUBLIC_ENABLE_ADVANCED_ROUTES === 'true'

export const MAIN_PRODUCT_ROUTES: MainRoute[] = [
  { href: '/', label: 'Today' },
  { href: '/watchlist', label: 'Watchlist' },
  { href: '/portfolio', label: 'Portfolio Coach' },
  { href: '/money', label: 'Money System' },
]
