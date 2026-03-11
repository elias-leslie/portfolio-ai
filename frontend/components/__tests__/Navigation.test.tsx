import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Navigation } from '../Navigation'

const usePathnameMock = vi.fn()

vi.mock('next/navigation', () => ({
  usePathname: () => usePathnameMock(),
}))

vi.mock('@/components/market/MarketStatusBadge', () => ({
  MarketStatusBadge: () => <div>Market Open</div>,
}))

describe('Navigation', () => {
  it('highlights the watchlist lane for nested symbol routes and exposes mobile route copy', () => {
    usePathnameMock.mockReturnValue('/symbols/VTI')

    render(<Navigation />)

    expect(
      screen.getAllByRole('link', {
        name: /Watchlist\. Track setups, score health, and symbol-specific follow-up work\./i,
      })[0],
    ).toHaveAttribute('aria-current', 'page')
    expect(
      screen.getByText(/track setups, score health, and symbol-specific follow-up work/i),
    ).toBeInTheDocument()
  })

  it('keeps all core routes reachable in the compact mobile navigation row', () => {
    usePathnameMock.mockReturnValue('/')

    render(<Navigation />)

    expect(screen.getAllByRole('link', { name: /today\./i }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: /watchlist\./i }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: /portfolio coach\./i }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: /money system\./i }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('link', { name: /status\./i }).length).toBeGreaterThan(0)
  })
})
