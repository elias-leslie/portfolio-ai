import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { WatchlistTableRow } from '../WatchlistTableRow'

vi.mock('@/components/watchlist/ExpandedRow', () => ({
  ExpandedRow: () => <div>Expanded Row</div>,
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

describe('WatchlistTableRow', () => {
  it('uses scanner-focused row content without source or decision clutter', () => {
    render(
      <table>
        <tbody>
          <WatchlistTableRow
            item={buildItem()}
            isExpanded={false}
            highlightedSymbol={null}
            recentlyUpdatedRows={new Set()}
            changedCells={{}}
            portfolioSymbols={new Set()}
            refreshStatus={undefined}
            isDeleting={false}
            userTimezone="America/New_York"
            rowRef={() => {}}
            onToggle={vi.fn()}
            onDelete={vi.fn()}
          />
        </tbody>
      </table>,
    )

    expect(
      screen.getByRole('button', { name: 'Expand MSFT details' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'MSFT' })).toHaveAttribute(
      'href',
      '/symbols/MSFT?tab=decision',
    )
    expect(screen.getByText('$411.55')).toBeInTheDocument()
    expect(screen.queryByText('$410.12')).not.toBeInTheDocument()
    // Amateur-first primary row content: company name, signal, rationale, score trendline
    expect(screen.getByText('Microsoft Corporation')).toBeInTheDocument()
    expect(
      screen.getByText('Momentum and earnings support more upside'),
    ).toBeInTheDocument()
    expect(screen.getByText('BUY')).toBeInTheDocument()
    expect(screen.getByText('Medium')).toBeInTheDocument()
    expect(screen.getByText('67')).toBeInTheDocument()
    expect(screen.getByLabelText('Data healthy')).toBeInTheDocument()
    // Quant/meta detail is demoted out of the primary row into the expand
    expect(screen.queryByText('P65')).not.toBeInTheDocument()
    expect(screen.queryByText('T69')).not.toBeInTheDocument()
    expect(screen.queryByText('Quote OK')).not.toBeInTheDocument()
    expect(screen.queryByText('Data 91%')).not.toBeInTheDocument()
    expect(screen.queryByText('D +1.2%')).not.toBeInTheDocument()
    expect(screen.queryByText('W -0.6%')).not.toBeInTheDocument()
    expect(screen.queryByText('VWAP +0.5%')).not.toBeInTheDocument()
    expect(screen.queryByText('Exit this position')).not.toBeInTheDocument()
    expect(
      screen.queryByText(/Jenny alert · Critical/i),
    ).not.toBeInTheDocument()
    expect(screen.queryByText('Fresh quote')).not.toBeInTheDocument()
    expect(screen.queryByText('yfinance')).not.toBeInTheDocument()
  })

  it('marks missing quote payloads as quote issues', () => {
    render(
      <table>
        <tbody>
          <WatchlistTableRow
            item={{ ...buildItem(), quote: null }}
            isExpanded={false}
            highlightedSymbol={null}
            recentlyUpdatedRows={new Set()}
            changedCells={{}}
            portfolioSymbols={new Set()}
            refreshStatus={undefined}
            isDeleting={false}
            userTimezone="America/New_York"
            rowRef={() => {}}
            onToggle={vi.fn()}
            onDelete={vi.fn()}
          />
        </tbody>
      </table>,
    )

    expect(screen.getByLabelText('Data needs attention')).toBeInTheDocument()
  })

  it('treats aging quotes as current enough for the scanner', () => {
    const item = {
      ...buildItem(),
      quote: {
        ...buildItem().quote,
        freshnessStatus: 'aging' as const,
        freshnessLabel: 'Aging quote',
      },
    }

    render(
      <table>
        <tbody>
          <WatchlistTableRow
            item={item}
            isExpanded={false}
            highlightedSymbol={null}
            recentlyUpdatedRows={new Set()}
            changedCells={{}}
            portfolioSymbols={new Set()}
            refreshStatus={undefined}
            isDeleting={false}
            userTimezone="America/New_York"
            rowRef={() => {}}
            onToggle={vi.fn()}
            onDelete={vi.fn()}
          />
        </tbody>
      </table>,
    )

    expect(screen.getByLabelText('Data healthy')).toBeInTheDocument()
    expect(screen.queryByText('Aging quote')).not.toBeInTheDocument()
  })

  it('treats recently cached stale-labeled quotes as current enough for the scanner', () => {
    const item = {
      ...buildItem(),
      quote: {
        ...buildItem().quote,
        cachedAt: new Date().toISOString(),
        freshnessStatus: 'stale' as const,
        freshnessLabel: 'Stale quote',
      },
    }

    render(
      <table>
        <tbody>
          <WatchlistTableRow
            item={item}
            isExpanded={false}
            highlightedSymbol={null}
            recentlyUpdatedRows={new Set()}
            changedCells={{}}
            portfolioSymbols={new Set()}
            refreshStatus={undefined}
            isDeleting={false}
            userTimezone="America/New_York"
            rowRef={() => {}}
            onToggle={vi.fn()}
            onDelete={vi.fn()}
          />
        </tbody>
      </table>,
    )

    expect(screen.getByLabelText('Data healthy')).toBeInTheDocument()
    expect(screen.queryByText('Stale quote')).not.toBeInTheDocument()
  })

  it('keeps the status healthy when only a low-weight pillar is partial', () => {
    const base = buildItem()
    const item = {
      ...base,
      dataQuality: {
        overallPct: 88,
        pillars: {
          ...base.dataQuality.pillars,
          options: {
            status: 'partial' as const,
            score: 70,
            details: '3 days in 7d, latest 2d ago',
          },
        },
      },
    }

    render(
      <table>
        <tbody>
          <WatchlistTableRow
            item={item}
            isExpanded={false}
            highlightedSymbol={null}
            recentlyUpdatedRows={new Set()}
            changedCells={{}}
            portfolioSymbols={new Set()}
            refreshStatus={undefined}
            isDeleting={false}
            userTimezone="America/New_York"
            rowRef={() => {}}
            onToggle={vi.fn()}
            onDelete={vi.fn()}
          />
        </tbody>
      </table>,
    )

    // 88% overall is healthy even though the options pillar is perpetually
    // partial — the partial detail belongs in the expanded breakdown, not the
    // headline status dot.
    expect(screen.getByLabelText('Data healthy')).toBeInTheDocument()
    expect(
      screen.queryByLabelText('Data partial or aging'),
    ).not.toBeInTheDocument()
  })

  it('shows the score-alert badge with a tooltip label when scoreAlert is set', () => {
    render(
      <table>
        <tbody>
          <WatchlistTableRow
            item={{ ...buildItem(), scoreAlert: true }}
            isExpanded={false}
            highlightedSymbol={null}
            recentlyUpdatedRows={new Set()}
            changedCells={{}}
            portfolioSymbols={new Set()}
            refreshStatus={undefined}
            isDeleting={false}
            userTimezone="America/New_York"
            rowRef={() => {}}
            onToggle={vi.fn()}
            onDelete={vi.fn()}
          />
        </tbody>
      </table>,
    )

    expect(
      screen.getByLabelText('Score changed >10 points in last 7 days'),
    ).toBeInTheDocument()
  })

  it('does not toggle the row when the delete action is clicked', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    const onDelete = vi.fn()

    render(
      <table>
        <tbody>
          <WatchlistTableRow
            item={buildItem()}
            isExpanded={false}
            highlightedSymbol={null}
            recentlyUpdatedRows={new Set()}
            changedCells={{}}
            portfolioSymbols={new Set(['MSFT'])}
            refreshStatus={undefined}
            isDeleting={false}
            userTimezone="America/New_York"
            rowRef={() => {}}
            onToggle={onToggle}
            onDelete={onDelete}
          />
        </tbody>
      </table>,
    )

    await user.click(screen.getByRole('button', { name: 'Delete MSFT' }))

    expect(onDelete).toHaveBeenCalledWith('item-1', 'MSFT')
    expect(onToggle).not.toHaveBeenCalled()
  })

  it('does not toggle the row when the symbol link is clicked', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()

    render(
      <table>
        <tbody>
          <WatchlistTableRow
            item={buildItem()}
            isExpanded={false}
            highlightedSymbol={null}
            recentlyUpdatedRows={new Set()}
            changedCells={{}}
            portfolioSymbols={new Set()}
            refreshStatus={undefined}
            isDeleting={false}
            userTimezone="America/New_York"
            rowRef={() => {}}
            onToggle={onToggle}
            onDelete={vi.fn()}
          />
        </tbody>
      </table>,
    )

    await user.click(screen.getByRole('link', { name: 'MSFT' }))

    expect(onToggle).not.toHaveBeenCalled()
  })

  it('toggles exactly once when the chevron action is clicked', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()

    render(
      <table>
        <tbody>
          <WatchlistTableRow
            item={buildItem()}
            isExpanded={false}
            highlightedSymbol={null}
            recentlyUpdatedRows={new Set()}
            changedCells={{}}
            portfolioSymbols={new Set()}
            refreshStatus={undefined}
            isDeleting={false}
            userTimezone="America/New_York"
            rowRef={() => {}}
            onToggle={onToggle}
            onDelete={vi.fn()}
          />
        </tbody>
      </table>,
    )

    await user.click(
      screen.getByRole('button', { name: 'Expand MSFT details' }),
    )

    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('toggles from the expand action with Enter and Space', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()

    render(
      <table>
        <tbody>
          <WatchlistTableRow
            item={buildItem()}
            isExpanded={false}
            highlightedSymbol={null}
            recentlyUpdatedRows={new Set()}
            changedCells={{}}
            portfolioSymbols={new Set()}
            refreshStatus={undefined}
            isDeleting={false}
            userTimezone="America/New_York"
            rowRef={() => {}}
            onToggle={onToggle}
            onDelete={vi.fn()}
          />
        </tbody>
      </table>,
    )

    screen.getByRole('button', { name: 'Expand MSFT details' }).focus()
    await user.keyboard('{Enter}')
    await user.keyboard(' ')

    expect(onToggle).toHaveBeenCalledTimes(2)
  })
})
