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

vi.mock('@/components/home/HomeActionQueueBadge', () => ({
  HomeActionQueueBadge: () => <button type="button">Actions 0</button>,
}))

vi.mock('@/components/status/FreshnessStatusBadge', () => ({
  FreshnessStatusBadge: () => <div>Live</div>,
}))

vi.mock('@/components/providers/ChatWidgetProvider', () => ({
  useChatWidget: () => ({
    enabled: true,
    ready: true,
    setEnabled: vi.fn(),
  }),
}))

describe('Navigation', () => {
  it('highlights the investing lane for nested symbol routes', () => {
    usePathnameMock.mockReturnValue('/symbols/VTI')

    render(<Navigation />)

    expect(
      screen.getAllByRole('link', {
        name: /Investing\. Track symbols, holdings, and portfolio decisions in one workspace\./i,
      })[0],
    ).toHaveAttribute('aria-current', 'page')
  })

  it('keeps the primary routes plus status reachable in navigation', () => {
    usePathnameMock.mockReturnValue('/')

    render(<Navigation />)

    expect(
      screen.getAllByRole('link', { name: /today\./i }).length,
    ).toBeGreaterThan(0)
    expect(
      screen.getAllByRole('link', { name: /investing\./i }).length,
    ).toBeGreaterThan(0)
    expect(
      screen.getAllByRole('link', { name: /money\./i }).length,
    ).toBeGreaterThan(0)
    expect(
      screen.getAllByRole('link', { name: /status\./i }).length,
    ).toBeGreaterThan(0)
  })
})
