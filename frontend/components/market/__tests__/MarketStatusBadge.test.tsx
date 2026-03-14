import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useMarketStatus } from '@/lib/hooks/useMarketIntelligence'
import { MarketStatusBadge } from '../MarketStatusBadge'

vi.mock('@/lib/hooks/useMarketIntelligence', () => ({
  useMarketStatus: vi.fn(),
}))

describe('MarketStatusBadge', () => {
  it('shows a loading indicator while fetching', () => {
    vi.mocked(useMarketStatus).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as never)

    render(<MarketStatusBadge />)

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('shows unavailable state on error', () => {
    vi.mocked(useMarketStatus).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('failed'),
    } as never)

    render(<MarketStatusBadge />)

    expect(screen.getByText('Status unavailable')).toBeInTheDocument()
  })

  it('displays the correct market status label', () => {
    vi.mocked(useMarketStatus).mockReturnValue({
      data: {
        status: 'open',
        currentTimeEt: '10:30 AM ET',
        lastTradingDay: '2026-03-14',
        nextTradingDay: '2026-03-15',
        isHoliday: false,
        holidayName: null,
        isEarlyClose: false,
        earlyCloseName: null,
      },
      isLoading: false,
      error: null,
    } as never)

    render(<MarketStatusBadge />)

    expect(screen.getByText('Market Open')).toBeInTheDocument()
  })

  it('displays closed status correctly', () => {
    vi.mocked(useMarketStatus).mockReturnValue({
      data: {
        status: 'closed',
        currentTimeEt: '6:00 PM ET',
        lastTradingDay: '2026-03-14',
        nextTradingDay: '2026-03-15',
        isHoliday: false,
        holidayName: null,
        isEarlyClose: false,
        earlyCloseName: null,
      },
      isLoading: false,
      error: null,
    } as never)

    render(<MarketStatusBadge />)

    expect(screen.getByText('Market Closed')).toBeInTheDocument()
  })
})
