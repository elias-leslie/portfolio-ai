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
})
