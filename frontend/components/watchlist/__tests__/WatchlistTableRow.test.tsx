import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { WatchlistTableRow } from '../WatchlistTableRow'

vi.mock('@/components/watchlist/ExpandedRow', () => ({
  ExpandedRow: () => <div>Expanded Row</div>,
}))

vi.mock('@/components/watchlist/SourceBadge', () => ({
  SourceBadge: () => <div>Source Badge</div>,
}))

vi.mock('@/components/watchlist/SparklineWithHistory', () => ({
  SparklineWithHistory: () => <div>Sparkline</div>,
}))

function buildItem() {
  return {
    id: 'item-1',
    symbol: 'MSFT',
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
  it('uses a concise expand aria-label instead of the full row contents', () => {
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
    expect(screen.getByText('Exit this position')).toBeInTheDocument()
    expect(screen.getByText(/Jenny alert · Critical/i)).toBeInTheDocument()
    expect(screen.getByText('$411.55')).toBeInTheDocument()
    expect(screen.queryByText('$410.12')).not.toBeInTheDocument()
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
