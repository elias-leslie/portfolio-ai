import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { StrategyLabWorkspace } from '@/components/strategy-lab/StrategyLabWorkspace'

const listState: any = vi.hoisted(() => ({
  items: [
    {
      symbol: 'VTI',
      action: 'wait',
      strategyTemplate: 'breakout_confirmation',
      primaryAccountTarget: null,
      updatedAt: '2026-04-18T12:00:00Z',
      helperText: null,
    },
  ],
  totalCount: 1,
  isLoading: false,
  error: null,
  refetch: vi.fn(async () => ({})),
}))

const detailState: any = vi.hoisted(() => ({
  bySymbol: {
    VTI: {
      symbol: 'VTI',
      action: 'wait',
      strategyTemplate: 'breakout_confirmation',
      primaryAccountTarget: null,
      updatedAt: '2026-04-18T12:00:00Z',
      helperText: null,
      whyBullets: [
        'Price setup: no entry trigger is active.',
        'Market context: trend filters are not confirming a new entry.',
        'Account context: unavailable.',
      ],
      watchItem: 'Watch: wait for a qualifying pullback or breakout.',
      ticket: null,
      backtestSnapshot: {
        status: 'ready',
        lookbackDays: 260,
        totalReturnPct: 1.23,
        buyHoldReturnPct: 0.45,
        excessReturnPct: 0.78,
        maxDrawdownPct: 5.67,
        tradeCount: 1,
        equityCurve: [{ date: '2026-04-18', equity: 50000 }],
        helperText: null,
      },
      review: { available: false, message: 'Review is unavailable right now.' },
    },
  },
  error: null,
  refetch: vi.fn(async () => ({})),
}))

function makeDetail(symbol: string, overrides: Record<string, any> = {}) {
  return {
    symbol,
    action: 'wait',
    strategyTemplate: 'breakout_confirmation',
    primaryAccountTarget: null,
    updatedAt: '2026-04-18T12:00:00Z',
    helperText: null,
    whyBullets: [
      'Price setup: no entry trigger is active.',
      'Market context: trend filters are not confirming a new entry.',
      'Account context: unavailable.',
    ],
    watchItem: 'Watch: wait for a qualifying pullback or breakout.',
    ticket: null,
    backtestSnapshot: {
      status: 'ready',
      lookbackDays: 260,
      totalReturnPct: 1.23,
      buyHoldReturnPct: 0.45,
      excessReturnPct: 0.78,
      maxDrawdownPct: 5.67,
      tradeCount: 1,
      equityCurve: [{ date: '2026-04-18', equity: 50000 }],
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
  useStrategyLabReview: () => ({ mutate: vi.fn() }),
}))

describe('StrategyLabWorkspace', () => {
  beforeEach(() => {
    listState.items = [
      {
        symbol: 'VTI',
        action: 'wait',
        strategyTemplate: 'breakout_confirmation',
        primaryAccountTarget: null,
        updatedAt: '2026-04-18T12:00:00Z',
        helperText: null,
      },
    ]
    listState.totalCount = 1
    listState.isLoading = false
    listState.error = null
    listState.refetch.mockClear()
    detailState.refetch.mockClear()
    detailState.error = null
    detailState.bySymbol = {
      VTI: makeDetail('VTI'),
    }
  })

  function renderWorkspace(initialSymbol: string | null = null) {
    const queryClient = new QueryClient()
    return render(
      <QueryClientProvider client={queryClient}>
        <StrategyLabWorkspace initialSymbol={initialSymbol} />
      </QueryClientProvider>,
    )
  }

  it('auto-selects the first item when no symbol query is present', async () => {
    renderWorkspace(null)
    await waitFor(() => {
      expect(screen.getByText('Best Signal')).toBeInTheDocument()
    })
    expect(
      screen.getByText('Price setup: no entry trigger is active.'),
    ).toBeInTheDocument()
  })

  it('shows the empty state when the list is empty and no detail is selected', async () => {
    listState.items = []
    listState.totalCount = 0
    renderWorkspace(null)
    await waitFor(() => {
      expect(
        screen.getByText('No symbols are ready for Strategy Lab yet.'),
      ).toBeInTheDocument()
    })
    expect(
      screen.getAllByRole('link', { name: 'Add Symbol' }).length,
    ).toBeGreaterThan(0)
  })

  it('shows a real list error instead of the empty state when the list query fails', async () => {
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
      screen.queryByText('No symbols are ready for Strategy Lab yet.'),
    ).not.toBeInTheDocument()
  })

  it('renders the five visible sections and fixed why/watch copy', async () => {
    renderWorkspace('VTI')
    await waitFor(() => {
      expect(screen.getByText('Best Signal')).toBeInTheDocument()
    })
    expect(screen.getByText('What To Do')).toBeInTheDocument()
    expect(screen.getByText('Why')).toBeInTheDocument()
    expect(screen.getByText('Backtest Snapshot')).toBeInTheDocument()
    expect(screen.getByText('Review')).toBeInTheDocument()
    expect(
      screen.getByText('Price setup: no entry trigger is active.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Watch: wait for a qualifying pullback or breakout.'),
    ).toBeInTheDocument()
  })

  it('manual refresh refetches list and detail together', async () => {
    renderWorkspace('VTI')
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: 'Refresh' }),
      ).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => {
      expect(listState.refetch).toHaveBeenCalled()
      expect(detailState.refetch).toHaveBeenCalled()
    })
  })

  it('uses the query symbol first but still lets the user switch symbols afterward', async () => {
    listState.items = [
      {
        symbol: 'VTI',
        action: 'wait',
        strategyTemplate: 'breakout_confirmation',
        primaryAccountTarget: null,
        updatedAt: '2026-04-18T12:00:00Z',
        helperText: null,
      },
      {
        symbol: 'NVDA',
        action: 'buy_now',
        strategyTemplate: 'breakout_confirmation',
        primaryAccountTarget: null,
        updatedAt: '2026-04-18T12:00:00Z',
        helperText: null,
      },
    ]
    listState.totalCount = 2
    detailState.bySymbol = {
      VTI: makeDetail('VTI'),
      NVDA: makeDetail('NVDA', {
        action: 'buy_now',
        whyBullets: [
          'Price setup: breakout is active for NVDA.',
          'Market context: the trend is confirming the move.',
          'Account context: cash is available for a starter position.',
        ],
        watchItem: 'Watch: stay above the recent breakout level.',
      }),
    }

    renderWorkspace('VTI')

    await waitFor(() => {
      expect(
        screen.getByText('Price setup: no entry trigger is active.'),
      ).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /NVDA/i }))

    await waitFor(() => {
      expect(
        screen.getByText('Price setup: breakout is active for NVDA.'),
      ).toBeInTheDocument()
    })

    expect(
      screen.queryByText('Price setup: no entry trigger is active.'),
    ).not.toBeInTheDocument()
  })
})
