import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AddSymbolModal } from '../AddSymbolModal'

const {
  createWatchlistItemMock,
  useTradingRulesMock,
  toastSuccessMock,
  toastWarningMock,
  toastErrorMock,
} = vi.hoisted(() => ({
  createWatchlistItemMock: vi.fn(),
  useTradingRulesMock: vi.fn(),
  toastSuccessMock: vi.fn(),
  toastWarningMock: vi.fn(),
  toastErrorMock: vi.fn(),
}))

vi.mock('@/lib/api/watchlist', () => ({
  createWatchlistItem: createWatchlistItemMock,
}))

vi.mock('@/lib/hooks/useRules', () => ({
  useTradingRules: (options?: { enabled?: boolean }) => useTradingRulesMock(options),
}))

vi.mock('sonner', () => ({
  toast: {
    success: toastSuccessMock,
    warning: toastWarningMock,
    error: toastErrorMock,
  },
}))

function renderModal(
  queryClient: QueryClient,
  onOpenChange = vi.fn(),
  currentCount = 5,
) {
  return {
    onOpenChange,
    ...render(
      <QueryClientProvider client={queryClient}>
        <AddSymbolModal
          open
          onOpenChange={onOpenChange}
          currentCount={currentCount}
        />
      </QueryClientProvider>,
    ),
  }
}

describe('AddSymbolModal', () => {
  beforeEach(() => {
    createWatchlistItemMock.mockReset()
    useTradingRulesMock.mockReset()
    toastSuccessMock.mockReset()
    toastWarningMock.mockReset()
    toastErrorMock.mockReset()
    useTradingRulesMock.mockReturnValue({
      data: {
        watchlistManagement: {
          maxWatchlistSize: 50,
        },
      },
    })
  })

  it('closes and clears the modal only after every symbol succeeds', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient()
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    const { onOpenChange } = renderModal(queryClient)

    createWatchlistItemMock.mockResolvedValueOnce({ symbol: 'MSFT' })

    await user.type(screen.getByLabelText('Symbols'), 'MSFT')
    await user.click(screen.getByRole('button', { name: /add 1 symbol/i }))

    await waitFor(() =>
      expect(createWatchlistItemMock).toHaveBeenCalledWith({
        symbol: 'MSFT',
        note: undefined,
      }),
    )

    expect(invalidateQueries).toHaveBeenCalledTimes(1)
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['watchlist', 'list'],
      refetchType: 'active',
    })
    expect(toastSuccessMock).toHaveBeenCalledWith('Added 1 symbol: MSFT')
    expect(toastWarningMock).not.toHaveBeenCalled()
    expect(toastErrorMock).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Symbols')).toHaveValue('')
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('keeps the modal open and preserves the input when every add fails', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient()
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    const { onOpenChange } = renderModal(queryClient)

    createWatchlistItemMock.mockRejectedValueOnce(new Error('Symbol VTI already in watchlist'))

    await user.type(screen.getByLabelText('Symbols'), 'VTI')
    await user.click(screen.getByRole('button', { name: /add 1 symbol/i }))

    await waitFor(() => expect(createWatchlistItemMock).toHaveBeenCalledTimes(1))

    expect(invalidateQueries).not.toHaveBeenCalled()
    expect(toastErrorMock).toHaveBeenCalledWith('Failed to add 1 symbol: VTI')
    expect(toastSuccessMock).not.toHaveBeenCalled()
    expect(toastWarningMock).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Symbols')).toHaveValue('VTI')
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
  })

  it('keeps only the failed and invalid symbols available for retry after a mixed submission', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient()
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    const { onOpenChange } = renderModal(queryClient)

    createWatchlistItemMock
      .mockResolvedValueOnce({ symbol: 'MSFT' })
      .mockRejectedValueOnce(new Error('Symbol VTI already in watchlist'))

    await user.type(
      screen.getByLabelText('Symbols'),
      'MSFT{enter}VTI{enter}TOO-LONG-SYMBOL',
    )
    await user.click(screen.getByRole('button', { name: /add 2 symbols/i }))

    await waitFor(() => expect(createWatchlistItemMock).toHaveBeenCalledTimes(2))

    expect(invalidateQueries).toHaveBeenCalledTimes(1)
    expect(toastWarningMock).toHaveBeenCalledWith(
      'Added 1 symbol. Failed to add 1 symbol: VTI',
    )
    expect(toastSuccessMock).not.toHaveBeenCalled()
    expect(toastErrorMock).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Symbols')).toHaveValue('VTI\nTOO-LONG-SYMBOL')
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
  })

  it('uses the backend trading rule for the watchlist size limit', () => {
    const queryClient = new QueryClient()

    useTradingRulesMock.mockReturnValue({
      data: {
        watchlistManagement: {
          maxWatchlistSize: 10,
        },
      },
    })

    renderModal(queryClient, vi.fn(), 9)

    expect(screen.getByText(/You have 9 of 10 symbols\./i)).toBeInTheDocument()
  })
})
