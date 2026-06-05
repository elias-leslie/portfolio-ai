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

function buildItem() {
  return {
    id: 'item-1',
    symbol: 'MSFT',
    companyName: 'Microsoft Corporation',
    narrativeHeadline: 'Momentum and earnings support more upside',
    note: 'Quality software business',
    source: 'manual' as const,
    createdAt: '2026-03-11T12:00:00Z',
    updatedAt: '2026-03-11T12:05:00Z',
    quote: {
      price: 411.55,
      source: 'yfinance',
      cachedAt: '2026-03-11T12:06:00Z',
      session: 'open',
      freshnessStatus: 'fresh',
      freshnessLabel: 'Fresh quote',
      error: null,
    },
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
          score: 100,
          details: 'Fresh',
        },
        technical: {
          status: 'complete' as const,
          score: 95,
          details: 'VWAP present',
        },
      },
    },
    priceTrends: [
      {
        key: 'D',
        label: '1M',
        returnPct: 1.2,
        startClose: 406.65,
        endClose: 411.55,
        startDate: '2026-02-11',
        endDate: '2026-03-11',
        endSource: 'day_bars',
        status: 'available',
        partial: false,
        pointCount: 22,
        series: [
          { date: '2026-02-11', close: 406.65 },
          { date: '2026-03-11', close: 411.55 },
        ],
      },
      {
        key: 'W',
        label: '3M',
        returnPct: -0.6,
        startClose: 414.03,
        endClose: 411.55,
        startDate: '2025-12-11',
        endDate: '2026-03-11',
        endSource: 'day_bars',
        status: 'available',
        partial: false,
        pointCount: 13,
        series: [
          { date: '2025-12-11', close: 414.03 },
          { date: '2026-03-11', close: 411.55 },
        ],
      },
    ],
    vwapSignal: {
      status: 'available',
      vwap: 409.5,
      price: 411.55,
      close: 410.12,
      distancePct: 0.5,
      asOfDate: '2026-03-11',
      closeAsOfDate: '2026-03-11',
      priceAsOf: '2026-03-11T12:06:00Z',
      priceSource: 'quote',
      source: 'day_bars',
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
    decision: {
      action: 'position_exit',
      headline: 'Exit this position',
      summary: 'Reduce risk now.',
      reasoning: ['The thesis broke.', 'Reduce risk now.'],
      sourceKind: 'jenny_alert',
      sourceLabel: 'Jenny alert',
      sourceTimestamp: '2026-03-11T12:05:00Z',
      severity: 'critical',
    },
  }
}

describe('WatchlistCard', () => {
  beforeEach(() => {
    expandedRowMock.mockClear()
  })

  it('shows scanner-focused mobile context without thesis, source, or history clutter', () => {
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

    expect(screen.getByRole('link', { name: 'MSFT' })).toHaveAttribute(
      'href',
      '/symbols/MSFT?tab=decision',
    )
    expect(screen.getByRole('link', { name: 'Open' })).toHaveAttribute(
      'href',
      '/symbols/MSFT?tab=decision',
    )
    expect(screen.getByText('Held')).toBeInTheDocument()
    expect(screen.getByText('Microsoft Corporation')).toBeInTheDocument()
    expect(
      screen.getByText('Momentum and earnings support more upside'),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Data healthy')).toBeInTheDocument()
    expect(
      screen.getByLabelText('Score changed >10 points in last 7 days'),
    ).toBeInTheDocument()
    expect(screen.getByText(/Refreshing 2\/5/i)).toBeInTheDocument()
    expect(screen.getByText('$411.55')).toBeInTheDocument()
    expect(screen.queryByText('Fresh quote')).not.toBeInTheDocument()
    expect(screen.queryByText('$410.12')).not.toBeInTheDocument()
    expect(screen.queryByText('+1.25%')).not.toBeInTheDocument()
    expect(screen.getByText('67')).toBeInTheDocument()
    expect(screen.getByText('BUY')).toBeInTheDocument()
    expect(screen.getByText('Medium')).toBeInTheDocument()
    expect(screen.getByText('Earnings soon')).toBeInTheDocument()
    // Quant/meta detail demoted out of the primary card into the expand
    expect(screen.queryByText('P65')).not.toBeInTheDocument()
    expect(screen.queryByText('T69')).not.toBeInTheDocument()
    expect(screen.queryByText('Quote OK')).not.toBeInTheDocument()
    expect(screen.queryByText('Data 91%')).not.toBeInTheDocument()
    expect(screen.queryByText('D +1.2%')).not.toBeInTheDocument()
    expect(screen.queryByText('W -0.6%')).not.toBeInTheDocument()
    expect(screen.queryByText('VWAP +0.5%')).not.toBeInTheDocument()
    expect(screen.queryByText('Decision')).not.toBeInTheDocument()
    expect(screen.queryByText('Exit this position')).not.toBeInTheDocument()
    expect(screen.queryByText('History item-1')).not.toBeInTheDocument()
    expect(screen.queryByText('yfinance')).not.toBeInTheDocument()
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
    expect(screen.queryByText('Held')).not.toBeInTheDocument()
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

    expect(screen.getByLabelText('Data partial or aging')).toBeInTheDocument()

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

    expect(screen.getByLabelText('Data needs attention')).toBeInTheDocument()
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
