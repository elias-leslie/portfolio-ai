'use client'

import {
  Briefcase,
  Eye,
  LayoutDashboard,
  Wallet,
} from 'lucide-react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { MarketStatusBadge } from '@/components/market/MarketStatusBadge'
import { MAIN_PRODUCT_ROUTES } from '@/lib/product-routes'
import { cn } from '@/lib/utils'

const routeIcons = {
  '/': LayoutDashboard,
  '/money': Wallet,
  '/portfolio': Briefcase,
  '/watchlist': Eye,
}

export function Navigation() {
  const pathname = usePathname()

  return <NavigationContent pathname={pathname} />
}

/**
 * Actual navigation content - only rendered on main app routes
 */
function NavigationContent({ pathname }: { pathname: string }) {
  return (
    <nav className="sticky top-0 z-50 border-b border-border/50 bg-surface/80 backdrop-blur-md supports-[backdrop-filter]:bg-surface/60">
      <div className="mx-auto h-16 w-full px-4 sm:px-6 lg:px-8">
        <div className="flex h-full items-center justify-between">
          {/* Logo */}
          <div className="flex items-center">
            <Link
              href="/"
              className="flex-shrink-0 rounded-md px-2 py-1 text-lg font-bold tracking-tight text-text transition-colors hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              Portfolio AI
            </Link>
          </div>

          {/* Main Navigation - Centered */}
          <div className="hidden lg:flex absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
            <div className="flex items-center gap-1 rounded-full bg-surface-muted/50 border border-border/50 p-1 shadow-sm backdrop-blur-sm">
              {MAIN_PRODUCT_ROUTES.map((link) => {
                const Icon = routeIcons[link.href]
                const isActive = pathname === link.href

                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    aria-current={isActive ? 'page' : undefined}
                    aria-label={link.label}
                    title={link.label}
                    className={cn(
                      'group flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus',
                      isActive
                        ? 'bg-primary text-primary-foreground shadow-md'
                        : 'text-text-muted hover:bg-surface hover:text-text hover:shadow-sm',
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
      </div>
    </nav>
  )
}
