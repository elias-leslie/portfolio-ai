import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useScoreHistory } from '@/lib/hooks/useWatchlist'
import { PriceSparkline } from '../PriceSparkline'

vi.mock('@/lib/hooks/useWatchlist', () => ({
  useScoreHistory: vi.fn(),
}))

const mockUseScoreHistory = vi.mocked(useScoreHistory)

function mockHistory(history: Array<Record<string, unknown>>) {
  mockUseScoreHistory.mockReturnValue({
    data: { itemId: 'item-1', symbol: 'MSFT', history },
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof useScoreHistory>)
}

describe('PriceSparkline', () => {
  it('renders a sparkline chart when the history carries prices', () => {
    mockHistory([
      {
        timestamp: '2026-03-01',
        overall: 60,
        priceScore: 50,
        technicalScore: 55,
        price: 400,
      },
      {
        timestamp: '2026-03-02',
        overall: 62,
        priceScore: 52,
        technicalScore: 58,
        price: 408,
      },
      {
        timestamp: '2026-03-03',
        overall: 64,
        priceScore: 54,
        technicalScore: 60,
        price: 412,
      },
    ])

    render(<PriceSparkline itemId="item-1" />)

    expect(screen.getByLabelText(/sparkline chart/i)).toBeInTheDocument()
    expect(screen.queryByText('—')).not.toBeInTheDocument()
  })

  it('renders an em dash when there is no history', () => {
    mockHistory([])

    render(<PriceSparkline itemId="item-1" />)

    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('renders an em dash when points have no price', () => {
    mockHistory([
      {
        timestamp: '2026-03-01',
        overall: 60,
        priceScore: 50,
        technicalScore: 55,
        price: null,
      },
    ])

    render(<PriceSparkline itemId="item-1" />)

    expect(screen.getByText('—')).toBeInTheDocument()
  })
})
