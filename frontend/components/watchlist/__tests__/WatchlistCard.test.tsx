import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { WatchlistCard } from '../WatchlistCard'

const expandedRowMock = vi.fn()

vi.mock('@/components/watchlist/ExpandedRow', () => ({
  ExpandedRow: (props: unknown) => {
    expandedRowMock(props)
    return <div>Expanded Row</div>
  },
}))

vi.mock('@/components/watchlist/SourceBadge', () => ({
  SourceBadge: () => <div>Source Badge</div>,
}))

vi.mock('@/components/watchlist/SparklineWithHistory', () => ({
  SparklineWithHistory: ({ itemId }: { itemId: string }) => <div>History {itemId}</div>,
}))

function buildItem() {
  return {
    id: 'item-1',
    symbol: 'MSFT',
    note: 'Quality software business',
    source: 'manual' as const,
    createdAt: '2026-03-11T12:00:00Z',
    updatedAt: '2026-03-11T12:05:00Z',
    riskLevel: 'Medium' as const,
    signalType: 'BUY' as const,
    recommendedStyle: 'Trend' as const,
    scoreAlert: true,
    priorityIndicators: [
      {
        icon: '!',
        label: 'Earnings soon',
        tooltip: 'An earnings date is approaching.',
        priority: 3,
        category: 'time_sensitive' as const,
      },
    ],
    dataQuality: {
      overallPct: 91,
      pillars: {
        price: {
          status: 'complete' as const,
          score: 1,
          details: 'Fresh',
        },
      },
    },
    currentScore: {
      overall: 67,
      price: {
        score: 65,
        weight: 1,
        stale: false,
        updatedAt: '2026-03-11T12:05:00Z',
        metadata: {
          price: 410.12,
          rawChangePct: 1.25,
          source: 'yfinance',
        },
      },
      technical: {
        score: 69,
        weight: 1,
        stale: false,
      },
    },
  }
}

describe('WatchlistCard', () => {
  beforeEach(() => {
    expandedRowMock.mockClear()
  })

  it('shows workspace navigation and mobile parity context', () => {
    render(
      <WatchlistCard
        item={buildItem()}
        portfolioSymbols={new Set(['MSFT'])}
        refreshStatus={{
          isRefreshing: true,
          currentSymbol: 'MSFT',
          processedItems: 2,
          totalItems: 5,
        }}
        userTimezone="America/New_York"
        onDelete={vi.fn()}
        isDeleting={false}
      />,
    )

    expect(screen.getByRole('link', { name: 'MSFT' })).toHaveAttribute('href', '/symbols/MSFT')
    expect(screen.getByRole('link', { name: 'Workspace' })).toHaveAttribute('href', '/symbols/MSFT')
    expect(screen.getByText('Portfolio')).toBeInTheDocument()
    expect(screen.getByText('Data quality 91%')).toBeInTheDocument()
    expect(screen.getByText(/Refreshing 2\/5/i)).toBeInTheDocument()
    expect(screen.getByText('Live price snapshot')).toBeInTheDocument()
    expect(screen.getByText('$410.12')).toBeInTheDocument()
    expect(screen.getByText('+1.25%')).toBeInTheDocument()
    expect(screen.getByText('🟢 BUY')).toBeInTheDocument()
    expect(screen.getByText('Style Trend')).toBeInTheDocument()
    expect(screen.getByText('Earnings soon')).toBeInTheDocument()
    expect(screen.getByText('History item-1')).toBeInTheDocument()
  })

  it('handles undefined refreshStatus and isRefreshing false', () => {
    render(
      <WatchlistCard
        item={buildItem()}
        portfolioSymbols={new Set(['MSFT'])}
        refreshStatus={undefined}
        userTimezone="America/New_York"
        onDelete={vi.fn()}
        isDeleting={false}
      />,
    )

    expect(screen.getByRole('link', { name: 'MSFT' })).toBeInTheDocument()
  })

  it('handles symbol not in portfolioSymbols', () => {
    render(
      <WatchlistCard
        item={buildItem()}
        portfolioSymbols={new Set(['AAPL'])}
        refreshStatus={{
          isRefreshing: false,
          currentSymbol: undefined,
          processedItems: 0,
          totalItems: 0,
        }}
        userTimezone="America/New_York"
        onDelete={vi.fn()}
        isDeleting={false}
      />,
    )

    expect(screen.getByRole('link', { name: 'MSFT' })).toBeInTheDocument()
    expect(screen.queryByText('Portfolio')).not.toBeInTheDocument()
  })

  it('handles undefined or zero dataQuality', () => {
    const item = buildItem()
    const { rerender } = render(
      <WatchlistCard
        item={{ ...item, dataQuality: undefined }}
        portfolioSymbols={new Set(['MSFT'])}
        refreshStatus={{
          isRefreshing: false,
          currentSymbol: undefined,
          processedItems: 0,
          totalItems: 0,
        }}
        userTimezone="America/New_York"
        onDelete={vi.fn()}
        isDeleting={false}
      />,
    )

    expect(screen.queryByText(/Data quality/i)).not.toBeInTheDocument()

    rerender(
      <WatchlistCard
        item={{ ...item, dataQuality: { overallPct: 0, pillars: {} } }}
        portfolioSymbols={new Set(['MSFT'])}
        refreshStatus={{
          isRefreshing: false,
          currentSymbol: undefined,
          processedItems: 0,
          totalItems: 0,
        }}
        userTimezone="America/New_York"
        onDelete={vi.fn()}
        isDeleting={false}
      />,
    )

    expect(screen.getByText('Data quality 0%')).toBeInTheDocument()
  })

  it('handles isDeleting true state', () => {
    render(
      <WatchlistCard
        item={buildItem()}
        portfolioSymbols={new Set(['MSFT'])}
        refreshStatus={{
          isRefreshing: false,
          currentSymbol: undefined,
          processedItems: 0,
          totalItems: 0,
        }}
        userTimezone="America/New_York"
        onDelete={vi.fn()}
        isDeleting={true}
      />,
    )

    expect(screen.getByRole('link', { name: 'MSFT' })).toBeInTheDocument()
  })

  it('passes refresh status into the expanded mobile details view', async () => {
    const user = userEvent.setup()

    render(
      <WatchlistCard
        item={buildItem()}
        portfolioSymbols={new Set(['MSFT'])}
        refreshStatus={{
          isRefreshing: true,
          currentSymbol: 'MSFT',
          processedItems: 2,
          totalItems: 5,
        }}
        userTimezone="America/New_York"
        onDelete={vi.fn()}
        isDeleting={false}
      />,
    )

    await user.click(screen.getByTestId('watchlist-card-expand'))

    expect(expandedRowMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        refreshStatus: expect.objectContaining({
          currentSymbol: 'MSFT',
          processedItems: 2,
          totalItems: 5,
        }),
      }),
    )
  })
})
