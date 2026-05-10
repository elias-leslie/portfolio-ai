import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { StrategyLabWorkspace } from '@/components/strategy-lab/StrategyLabWorkspace'

const decisionMutate: any = vi.hoisted(() => vi.fn())

const listState: any = vi.hoisted(() => ({
  items: [] as any[],
  unavailableItems: [] as any[],
  discoveries: [] as any[],
  totalCount: 0,
  isLoading: false,
  error: null as Error | null,
  refetch: vi.fn(async () => ({})),
}))

const detailState: any = vi.hoisted(() => ({
  bySymbol: {} as Record<string, any>,
  error: null as Error | null,
  refetch: vi.fn(async () => ({})),
}))

function makeListItem(symbol: string, overrides: Record<string, any> = {}) {
  return {
    symbol,
    action: 'buy_now',
    strategyTemplate: 'breakout_confirmation',
    primaryAccountTarget: {
      accountId: 'acct-1',
      accountName: 'ROTH IRA',
      accountType: 'Roth',
      cashBalance: 12500,
      heldMarketValue: null,
    },
    updatedAt: '2026-05-10T12:00:00Z',
    helperText: null,
    signal: {
      strategyId: 'strat-1',
      strategyName: 'MeanReversion v3',
      strategyType: 'mean_reversion',
      signalStrength: 8,
      signalStatus: 'valid',
      signalReasons: ['RSI < 30', 'Above 200d SMA'],
      signalDate: '2026-05-09',
      expectedSharpe: 1.42,
      validationType: 'both',
      risk: {
        entryPrice: 100,
        currentPrice: 102,
        priceChangePct: 2,
        stopLoss: 95,
        targetPrice: 115,
        riskRewardRatio: 2.6,
      },
      suggestedSizeDollars: 5000,
      suggestedSizeShares: 50,
    },
    backtestStatus: 'ready',
    backtestHelperText: null,
    backtestLookbackDays: 260,
    ...overrides,
  }
}

function makeDetail(symbol: string, overrides: Record<string, any> = {}) {
  const base = makeListItem(symbol)
  return {
    ...base,
    whyBullets: [
      'Signal: MeanReversion v3 fired strength 8/10.',
      'Edge: expected Sharpe 1.42.',
    ],
    watchItem: 'Watch: stop at $95.00, target $115.00 (R:R 2.60).',
    ticket: {
      accountId: 'acct-1',
      accountName: 'ROTH IRA',
      action: 'buy_now',
      dollars: 5000,
      estimatedShares: 49,
      firstTrancheDollars: 5000,
      helperText: null,
    },
    backtestSnapshot: {
      status: 'ready',
      lookbackDays: 260,
      requestedStartDate: null,
      requestedEndDate: null,
      availableStartDate: null,
      availableEndDate: null,
      totalReturnPct: 12.5,
      buyHoldReturnPct: 6.0,
      excessReturnPct: 6.5,
      maxDrawdownPct: 5.6,
      tradeCount: 14,
      equityCurve: [
        { date: '2024-01-01', equity: 50000 },
        { date: '2024-06-01', equity: 52000 },
        { date: '2026-05-09', equity: 56250 },
      ],
      buyHoldCurve: [
        { date: '2024-01-01', equity: 50000 },
        { date: '2024-06-01', equity: 51000 },
        { date: '2026-05-09', equity: 53000 },
      ],
      helperText: null,
    },
    review: { available: false, message: 'Review is unavailable right now.' },
    ...overrides,
  }
}

vi.mock('@/lib/hooks/useStrategyLab', () => ({
  useStrategyLabList: () => ({
    data: {
      items: listState.items,
      unavailableItems: listState.unavailableItems,
      discoveries: listState.discoveries,
      totalCount: listState.totalCount,
    },
    isLoading: listState.isLoading,
    error: listState.error,
    refetch: listState.refetch,
  }),
  useStrategyLabDetail: (symbol: string | null) => ({
    data: symbol ? (detailState.bySymbol[symbol] ?? null) : null,
    error: detailState.error,
    refetch: detailState.refetch,
  }),
  useStrategyLabReview: () => ({ mutate: vi.fn(), isPending: false }),
  useStrategyLabDecision: () => ({ mutate: decisionMutate, isPending: false }),
}))

vi.mock('@/lib/hooks/useWatchlist', () => ({
  useWatchlist: () => ({ data: { items: [] } }),
  watchlistKeys: { list: () => ['watchlist'] },
}))

describe('StrategyLabWorkspace', () => {
  beforeEach(() => {
    listState.items = [makeListItem('VTI')]
    listState.unavailableItems = []
    listState.discoveries = []
    listState.totalCount = 1
    listState.isLoading = false
    listState.error = null
    listState.refetch.mockClear()
    detailState.refetch.mockClear()
    detailState.error = null
    detailState.bySymbol = { VTI: makeDetail('VTI') }
    decisionMutate.mockClear()
  })

  function renderWorkspace(initialSymbol: string | null = null) {
    const queryClient = new QueryClient()
    return render(
      <QueryClientProvider client={queryClient}>
        <StrategyLabWorkspace initialSymbol={initialSymbol} />
      </QueryClientProvider>,
    )
  }

  it('auto-selects the first item and renders the proof hero + ticket', async () => {
    renderWorkspace(null)
    await waitFor(() => {
      expect(screen.getAllByText('Buy now').length).toBeGreaterThan(0)
    })
    expect(screen.getAllByText(/MeanReversion v3/).length).toBeGreaterThan(0)
    expect(screen.getByText('First tranche')).toBeInTheDocument()
    expect(screen.getByText('Proof')).toBeInTheDocument()
  })

  it('shows the cold-start explainer when nothing is in scope and no discoveries', async () => {
    listState.items = []
    listState.totalCount = 0
    renderWorkspace(null)
    await waitFor(() => {
      expect(
        screen.getByText(/Strategy Lab surfaces calls only after/),
      ).toBeInTheDocument()
    })
    expect(
      screen.getAllByRole('button', { name: /Add symbol/ }).length,
    ).toBeGreaterThan(0)
  })

  it('renders the cold-start discovery hero when discoveries exist', async () => {
    listState.items = []
    listState.totalCount = 0
    listState.discoveries = [
      {
        symbol: 'NVDA',
        strategyName: 'Momentum v1',
        strategyType: 'breakout',
        signalStrength: 9,
        signalStatus: 'valid',
        validationType: 'backtest',
        expectedSharpe: 1.6,
        risk: {
          entryPrice: 600,
          currentPrice: 605,
          priceChangePct: 0.8,
          stopLoss: 580,
          targetPrice: 700,
          riskRewardRatio: 4,
        },
        backtestSnapshot: null,
      },
    ]
    renderWorkspace(null)
    await waitFor(() => {
      expect(screen.getByText(/No tracked symbols yet/)).toBeInTheDocument()
    })
    expect(screen.getAllByText('NVDA').length).toBeGreaterThan(0)
    expect(
      screen.getByRole('button', { name: /Track NVDA/ }),
    ).toBeInTheDocument()
  })

  it('shows the list error instead of any state branch when the query fails', async () => {
    listState.items = []
    listState.totalCount = 0
    listState.error = new Error('Strategy Lab list is unavailable right now.')
    renderWorkspace(null)
    await waitFor(() => {
      expect(
        screen.getByText('Strategy Lab list is unavailable right now.'),
      ).toBeInTheDocument()
    })
    expect(
      screen.queryByText(/Strategy Lab surfaces calls only after/),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/No tracked symbols yet/)).not.toBeInTheDocument()
  })

  it('renders partial-data issues alongside available items', async () => {
    listState.unavailableItems = [
      {
        symbol: 'AMZN',
        reason: 'insufficient_history',
        message: 'Not enough daily history to judge this strategy yet.',
        requestedStartDate: '2021-04-23',
        requestedEndDate: '2026-04-23',
        availableStartDate: '2024-01-02',
        availableEndDate: '2026-04-23',
        lookbackDays: 180,
      },
    ]
    renderWorkspace('VTI')
    await waitFor(() => {
      expect(screen.getByText('Partial data')).toBeInTheDocument()
    })
    expect(screen.getByText('AMZN')).toBeInTheDocument()
    expect(screen.getByText('History')).toBeInTheDocument()
  })

  it('fires a decision when Act now is clicked', async () => {
    renderWorkspace('VTI')
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Act now' }),
      ).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Act now' }))
    expect(decisionMutate).toHaveBeenCalledTimes(1)
    expect(decisionMutate.mock.calls[0]?.[0]).toEqual({ action: 'act_now' })
  })

  it('manual refresh re-fetches list and detail together', async () => {
    renderWorkspace('VTI')
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /Refresh/ }),
      ).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: /Refresh/ }))
    await waitFor(() => {
      expect(listState.refetch).toHaveBeenCalled()
      expect(detailState.refetch).toHaveBeenCalled()
    })
  })
})
