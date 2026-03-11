import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { WatchlistCard } from '../WatchlistCard'

vi.mock('@/components/watchlist/ExpandedRow', () => ({
  ExpandedRow: () => <div>Expanded Row</div>,
}))

vi.mock('@/components/watchlist/SourceBadge', () => ({
  SourceBadge: () => <div>Source Badge</div>,
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
    scoreAlert: true,
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
    expect(screen.getByText('DQ 91%')).toBeInTheDocument()
    expect(screen.getByText(/Refreshing 2\/5/i)).toBeInTheDocument()
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

    expect(screen.queryByText(/DQ/)).not.toBeInTheDocument()

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

    expect(screen.getByText('DQ 0%')).toBeInTheDocument()
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
})
