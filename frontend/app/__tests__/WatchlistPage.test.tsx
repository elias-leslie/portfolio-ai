import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const useWatchlistMock = vi.fn()
const useRefreshWatchlistMock = vi.fn()
const useWatchlistFiltersMock = vi.fn()

vi.mock('@/lib/hooks/useWatchlist', () => ({
  useWatchlist: () => useWatchlistMock(),
  useRefreshWatchlist: () => useRefreshWatchlistMock(),
}))

vi.mock('@/components/watchlist/useWatchlistFilters', () => ({
  useWatchlistFilters: (items: unknown[]) => useWatchlistFiltersMock(items),
}))

vi.mock('@/components/watchlist/WatchlistFilterBar', () => ({
  WatchlistFilterBar: ({ onReset }: { onReset: () => void }) => (
    <button type="button" onClick={onReset}>
      Reset filters
    </button>
  ),
}))

vi.mock('@/components/watchlist/WatchlistSearchBar', () => ({
  WatchlistSearchBar: () => <div>Search Bar</div>,
}))

vi.mock('@/components/watchlist/WatchlistTable', () => ({
  WatchlistTable: () => <div>Watchlist Table</div>,
}))

vi.mock('@/components/watchlist/AddSymbolModal', () => ({
  AddSymbolModal: ({
    open,
  }: {
    open: boolean
    onOpenChange: (open: boolean) => void
    currentCount: number
  }) => <div>{open ? 'Add Symbol Modal Open' : 'Add Symbol Modal Closed'}</div>,
}))

describe('WatchlistPage', () => {
  beforeEach(() => {
    useRefreshWatchlistMock.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    })
    useWatchlistMock.mockReturnValue({
      data: {
        items: [],
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    })
    useWatchlistFiltersMock.mockReturnValue({
      styleFilter: 'all',
      setStyleFilter: vi.fn(),
      signalFilter: 'all',
      setSignalFilter: vi.fn(),
      riskFilter: 'all',
      setRiskFilter: vi.fn(),
      searchQuery: '',
      setSearchQuery: vi.fn(),
      filteredItems: [],
      counts: { style: {}, signal: {}, risk: {} },
      hasActiveFilters: false,
      resetFilters: vi.fn(),
    })
  })

  it('retries the watchlist query from the shared error state', async () => {
    const user = userEvent.setup()
    const refetch = vi.fn()
    useWatchlistMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('backend down'),
      refetch,
      isFetching: false,
    })

    const { default: WatchlistPage } = await import('../watchlist/page')

    render(<WatchlistPage />)

    await user.click(screen.getByRole('button', { name: 'Retry watchlist' }))

    expect(refetch).toHaveBeenCalled()
  })

  it('shows a filtered empty state and lets the user reset filters', async () => {
    const user = userEvent.setup()
    const resetFilters = vi.fn()
    useWatchlistMock.mockReturnValue({
      data: {
        items: [{ id: '1', symbol: 'MSFT' }],
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      isFetching: false,
    })
    useWatchlistFiltersMock.mockReturnValue({
      styleFilter: 'all',
      setStyleFilter: vi.fn(),
      signalFilter: 'BUY',
      setSignalFilter: vi.fn(),
      riskFilter: 'all',
      setRiskFilter: vi.fn(),
      searchQuery: 'nvda',
      setSearchQuery: vi.fn(),
      filteredItems: [],
      counts: { style: {}, signal: {}, risk: {} },
      hasActiveFilters: true,
      resetFilters,
    })

    const { default: WatchlistPage } = await import('../watchlist/page')

    render(<WatchlistPage />)

    expect(screen.getByText('No symbols match the current filters')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Reset filters' }))

    expect(resetFilters).toHaveBeenCalled()
  })

  it('opens the add-symbol modal from the empty watchlist state', async () => {
    const user = userEvent.setup()
    const { default: WatchlistPage } = await import('../watchlist/page')

    render(<WatchlistPage />)

    expect(screen.getByText('Add Symbol Modal Closed')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: 'Add Symbol' })[0])

    expect(screen.getByText('Add Symbol Modal Open')).toBeInTheDocument()
  })
})
