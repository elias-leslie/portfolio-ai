'use client'

import {
  Briefcase,
  Eye,
  LayoutDashboard,
  Radar,
  Wallet,
} from 'lucide-react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { MarketStatusBadge } from '@/components/market/MarketStatusBadge'
import {
  MAIN_PRODUCT_ROUTES,
  resolveMainProductRoute,
} from '@/lib/product-routes'
import { cn } from '@/lib/utils'

const routeIcons = {
  '/': LayoutDashboard,
  '/money': Wallet,
  '/portfolio': Briefcase,
  '/watchlist': Eye,
  '/status': Radar,
}

export function Navigation() {
  const pathname = usePathname()

  return <NavigationContent pathname={pathname} />
}

/**
 * Actual navigation content - only rendered on main app routes
 */
function NavigationContent({ pathname }: { pathname: string }) {
  const activeRoute = resolveMainProductRoute(pathname)

  return (
    <nav className="sticky top-0 z-50 border-b border-border/50 bg-surface/80 backdrop-blur-md supports-[backdrop-filter]:bg-surface/60">
      <div className="mx-auto w-full px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <div className="flex items-center">
            <Link
              href="/"
              className="flex-shrink-0 rounded-md px-2 py-1 font-display text-[1.35rem] font-medium italic tracking-tight text-text transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              Portfolio AI
            </Link>
          </div>

          {/* Main Navigation - Centered */}
          <div className="absolute left-1/2 top-1/2 hidden -translate-x-1/2 -translate-y-1/2 lg:flex">
            <div className="flex items-center gap-1 rounded-full border border-border/50 bg-surface-muted/50 p-1 shadow-sm backdrop-blur-sm">
              {MAIN_PRODUCT_ROUTES.map((link) => {
                const Icon = routeIcons[link.href]
                const isActive = activeRoute.href === link.href

                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    aria-current={isActive ? 'page' : undefined}
                    aria-label={`${link.label}. ${link.description}`}
                    title={`${link.label} - ${link.description}`}
                    className={cn(
                      'group flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus',
                      isActive
                        ? 'bg-primary text-primary-foreground shadow-[0_0_16px_-4px] shadow-primary/40'
                        : 'text-text-muted hover:bg-surface/80 hover:text-text',
                    )}
                  >
                    <Icon
                      className={cn(
                        'size-4 transition-transform group-hover:scale-110',
                        isActive && 'text-primary-foreground',
                      )}
                      aria-hidden
                      suppressHydrationWarning
                    />
                    <span>{link.label}</span>
                  </Link>
                )
              })}
            </div>
          </div>

          {/* Utility Items */}
          <div className="flex items-center gap-1 sm:gap-2">
            <div className="hidden sm:block">
              <MarketStatusBadge />
            </div>
          </div>
        </div>

        <div className="border-t border-border/40 py-3 lg:hidden">
          <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {MAIN_PRODUCT_ROUTES.map((link) => {
              const Icon = routeIcons[link.href]
              const isActive = activeRoute.href === link.href

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={isActive ? 'page' : undefined}
                  aria-label={`${link.label}. ${link.description}`}
                  className={cn(
                    'flex shrink-0 items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus active:scale-[0.97]',
                    isActive
                      ? 'border-primary/40 bg-primary/10 text-text shadow-[0_0_12px_-4px] shadow-primary/25'
                      : 'border-border/40 bg-surface/60 text-text-muted hover:border-border/60 hover:bg-surface/80 hover:text-text',
                  )}
                >
                  <Icon className="size-4" aria-hidden suppressHydrationWarning />
                  <span>{link.label}</span>
                </Link>
              )
            })}
          </div>
          <p className="mt-2 text-sm text-text-muted">{activeRoute.description}</p>
        </div>
      </div>
    </nav>
  )
}
