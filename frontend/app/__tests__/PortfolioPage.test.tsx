import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, type Mock, vi } from 'vitest'
import {
  useAccounts,
  useAddPosition,
  useCreateAccount,
  usePortfolio,
} from '@/lib/hooks/usePortfolio'
import {
  useRefreshStatus,
  useRefreshWatchlist,
  useWatchlist,
} from '@/lib/hooks/useWatchlist'

vi.mock('@/components/portfolio/AccountsWithPositions', () => {
  const MockComponent = ({
    onAddAccount,
    onAddPosition,
  }: {
    onAddAccount?: () => void
    onAddPosition?: (accountId?: string) => void
  }) => (
    <div>
      <button type="button" onClick={onAddAccount}>
        Open Add Account
      </button>
      <button type="button" onClick={() => onAddPosition?.('acct-2')}>
        Open Add Position
      </button>
      <button type="button" onClick={() => onAddPosition?.()}>
        Open Generic Add Position
      </button>
    </div>
  )

  return {
    AccountsWithPositions: MockComponent,
    AccountsWithPositionsContent: MockComponent,
  }
})

vi.mock('@/components/watchlist/useWatchlistFilters', () => ({
  useWatchlistFilters: () => ({
    styleFilter: 'all',
    setStyleFilter: vi.fn(),
    signalFilter: 'all',
    setSignalFilter: vi.fn(),
    riskFilter: 'all',
    setRiskFilter: vi.fn(),
    searchQuery: '',
    setSearchQuery: vi.fn(),
    filteredItems: [{ id: 'watch-1', symbol: 'VTI' }],
    counts: { style: {}, signal: {}, risk: {} },
    hasActiveFilters: false,
    resetFilters: vi.fn(),
  }),
}))

vi.mock('@/components/watchlist/WatchlistFilterBar', () => ({
  WatchlistFilterBar: () => <div>Filter Bar</div>,
}))

vi.mock('@/components/watchlist/WatchlistSearchBar', () => ({
  WatchlistSearchBar: () => <div>Search Bar</div>,
}))

vi.mock('@/components/watchlist/WatchlistTable', () => ({
  WatchlistTable: () => <div>Watchlist Table</div>,
}))

vi.mock('@/components/watchlist/WatchlistStateViews', () => ({
  WatchlistEmptyState: () => <div>Watchlist Empty State</div>,
  WatchlistErrorView: () => <div>Watchlist Error View</div>,
  WatchlistLoadingSkeleton: () => <div>Watchlist Loading</div>,
}))

vi.mock('@/components/watchlist/AddSymbolModal', () => ({
  AddSymbolModal: ({ open }: { open: boolean }) => (
    <div>{open ? 'Add Symbol Modal Open' : 'Add Symbol Modal Closed'}</div>
  ),
}))

vi.mock('@/components/portfolio/InvestingNewsPanel', () => ({
  InvestingNewsPanel: ({ isInputLoading }: { isInputLoading?: boolean }) => (
    <div>
      Investing News Panel {isInputLoading ? 'Loading Inputs' : 'Ready Inputs'}
    </div>
  ),
}))

vi.mock('@/lib/hooks/usePortfolio', () => ({
  useAccounts: vi.fn(),
  useAddPosition: vi.fn(),
  useCreateAccount: vi.fn(),
  usePortfolio: vi.fn(),
}))

vi.mock('@/lib/hooks/useWatchlist', () => ({
  useWatchlist: vi.fn(),
  useRefreshWatchlist: vi.fn(),
  useRefreshStatus: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const mockUseAccounts = useAccounts as unknown as Mock
const mockUseAddPosition = useAddPosition as unknown as Mock
const mockUseCreateAccount = useCreateAccount as unknown as Mock
const mockUsePortfolio = usePortfolio as unknown as Mock
const mockUseWatchlist = useWatchlist as unknown as Mock
const mockUseRefreshWatchlist = useRefreshWatchlist as unknown as Mock
const mockUseRefreshStatus = useRefreshStatus as unknown as Mock

describe('PortfolioPage', () => {
  const addPositionMutate = vi.fn()
  const createAccountMutate = vi.fn()

  beforeEach(() => {
    window.history.replaceState({}, '', '/portfolio')
    addPositionMutate.mockReset()
    createAccountMutate.mockReset()

    mockUseAccounts.mockReturnValue({
      data: [
        {
          id: 'acct-1',
          name: 'Brokerage',
          accountType: 'Taxable',
          cashBalance: 0,
          createdAt: '2026-03-11T00:00:00Z',
          updatedAt: '2026-03-11T00:00:00Z',
        },
        {
          id: 'acct-2',
          name: 'Roth IRA',
          accountType: 'Roth',
          cashBalance: 0,
          createdAt: '2026-03-11T00:00:00Z',
          updatedAt: '2026-03-11T00:00:00Z',
        },
      ],
      isLoading: false,
    })
    mockUseAddPosition.mockReturnValue({
      mutate: addPositionMutate,
      isPending: false,
    })
    mockUseCreateAccount.mockReturnValue({
      mutate: createAccountMutate,
      isPending: false,
    })
    mockUsePortfolio.mockReturnValue({
      data: {
        positions: [
          {
            id: 'position-1',
            symbol: 'VTI',
            accountId: 'acct-1',
            shares: 10,
            costBasis: 200,
            currentPrice: 220,
            currentValue: 2200,
            gain: 200,
            gainPct: 10,
            positionType: 'long',
            createdAt: '2026-03-11T00:00:00Z',
            updatedAt: '2026-03-11T00:00:00Z',
          },
        ],
        totalValue: 2200,
        totalCostBasis: 2000,
        totalGain: 200,
        totalGainPct: 10,
        cashBalanceTotal: 300,
      },
      isLoading: false,
    })
    mockUseWatchlist.mockReturnValue({
      data: {
        items: [{ id: 'watch-1', symbol: 'VTI', scoreAlert: false }],
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    })
    mockUseRefreshWatchlist.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    })
    mockUseRefreshStatus.mockReturnValue({
      data: { isRefreshing: false },
    })
  })

  it('submits a normalized account name from the add-account dialog', async () => {
    const user = userEvent.setup()
    createAccountMutate.mockImplementation(
      (
        _payload: unknown,
        options?: { onSuccess?: () => void; onError?: (error: Error) => void },
      ) => {
        options?.onSuccess?.()
      },
    )

    const { default: PortfolioPage } = await import('../portfolio/page')

    render(<PortfolioPage />)

    await user.click(screen.getByRole('tab', { name: 'Holdings' }))
    await user.click(screen.getByRole('button', { name: 'Open Add Account' }))
    await user.type(
      screen.getByLabelText('Account Name'),
      '  Joint   Brokerage  ',
    )
    await user.click(screen.getByRole('button', { name: 'Create Account' }))

    expect(createAccountMutate).toHaveBeenCalledWith(
      {
        name: 'Joint Brokerage',
        accountType: 'Taxable',
      },
      expect.objectContaining({
        onSuccess: expect.any(Function),
      }),
    )
  })

  it('normalizes symbol and keeps the requested account when adding a position', async () => {
    const user = userEvent.setup()
    addPositionMutate.mockImplementation(
      (
        _payload: unknown,
        options?: { onSuccess?: () => void; onError?: (error: Error) => void },
      ) => {
        options?.onSuccess?.()
      },
    )

    const { default: PortfolioPage } = await import('../portfolio/page')

    render(<PortfolioPage />)

    await user.click(screen.getByRole('tab', { name: 'Holdings' }))
    await user.click(screen.getByRole('button', { name: 'Open Add Position' }))
    await user.type(screen.getByLabelText('Symbol'), ' msft ')
    await user.type(screen.getByLabelText('Shares'), '10')
    await user.type(screen.getByLabelText('Cost Basis (per share)'), '123.45')
    await user.click(screen.getByRole('button', { name: 'Add Position' }))

    expect(addPositionMutate).toHaveBeenCalledWith(
      {
        accountId: 'acct-2',
        symbol: 'MSFT',
        shares: 10,
        costBasis: 123.45,
        positionType: 'long',
      },
      expect.objectContaining({
        onSuccess: expect.any(Function),
      }),
    )
  })

  it('preselects the only account for the generic add-position action', async () => {
    const user = userEvent.setup()
    mockUseAccounts.mockReturnValue({
      data: [
        {
          id: 'acct-1',
          name: 'Brokerage',
          accountType: 'Taxable',
          cashBalance: 0,
          createdAt: '2026-03-11T00:00:00Z',
          updatedAt: '2026-03-11T00:00:00Z',
        },
      ],
      isLoading: false,
    })

    const { default: PortfolioPage } = await import('../portfolio/page')

    render(<PortfolioPage />)

    await user.click(screen.getByRole('tab', { name: 'Holdings' }))
    await user.click(
      screen.getByRole('button', { name: 'Open Generic Add Position' }),
    )

    await waitFor(() => {
      expect(
        screen.getByRole('combobox', { name: 'Account' }),
      ).toHaveTextContent('Brokerage (Taxable)')
    })
  })

  it('marks submit actions busy while portfolio mutations are pending', async () => {
    const user = userEvent.setup()
    mockUseAddPosition.mockReturnValue({
      mutate: addPositionMutate,
      isPending: true,
    })
    mockUseCreateAccount.mockReturnValue({
      mutate: createAccountMutate,
      isPending: true,
    })

    const { default: PortfolioPage } = await import('../portfolio/page')

    render(<PortfolioPage />)

    await user.click(screen.getByRole('tab', { name: 'Holdings' }))
    await user.click(screen.getByRole('button', { name: 'Open Add Account' }))
    expect(screen.getByRole('button', { name: 'Creating...' })).toHaveAttribute(
      'aria-busy',
      'true',
    )

    await user.click(screen.getByRole('button', { name: 'Close' }))
    await user.click(screen.getByRole('tab', { name: 'Holdings' }))
    await user.click(screen.getByRole('button', { name: 'Open Add Position' }))
    expect(screen.getByRole('button', { name: 'Adding...' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
  })

  it('keeps the header add-position action disabled until an account exists', async () => {
    mockUseAccounts.mockReturnValue({
      data: [],
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    })

    const { default: PortfolioPage } = await import('../portfolio/page')

    render(<PortfolioPage />)

    expect(
      screen.queryByRole('button', { name: 'Add Position' }),
    ).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'News' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Symbols' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Holdings' })).toBeInTheDocument()
  })

  it('hides symbol filters and search until watchlist data finishes loading', async () => {
    const user = userEvent.setup()
    mockUseWatchlist.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
      isFetching: true,
    })

    const { default: PortfolioPage } = await import('../portfolio/page')

    render(<PortfolioPage />)

    await user.click(screen.getByRole('tab', { name: 'Symbols' }))

    expect(screen.getByText('Watchlist Loading')).toBeInTheDocument()
    expect(screen.queryByText('Filter Bar')).not.toBeInTheDocument()
    expect(screen.queryByText('Search Bar')).not.toBeInTheDocument()
    expect(screen.queryByText('Watchlist Empty State')).not.toBeInTheDocument()
  })

  it('keeps news in loading state until portfolio and watchlist inputs resolve', async () => {
    const user = userEvent.setup()
    mockUsePortfolio.mockReturnValue({
      data: undefined,
      isLoading: true,
    })
    mockUseWatchlist.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
      isFetching: true,
    })

    const { default: PortfolioPage } = await import('../portfolio/page')

    render(<PortfolioPage />)

    await user.click(screen.getByRole('tab', { name: 'News' }))

    expect(
      screen.getByText(/Investing News Panel Loading Inputs/),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Ready Inputs/)).not.toBeInTheDocument()
  })
})
