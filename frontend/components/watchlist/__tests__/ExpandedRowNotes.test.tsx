import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ExpandedRowNotes } from '../ExpandedRowNotes'

const mutate = vi.fn()
const useUpdateWatchlistItemMock = vi.fn()

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@/lib/hooks/useWatchlist', () => ({
  useUpdateWatchlistItem: () =>
    useUpdateWatchlistItemMock() ?? {
      mutate,
      isPending: false,
    },
}))

describe('ExpandedRowNotes', () => {
  beforeEach(() => {
    mutate.mockReset()
    useUpdateWatchlistItemMock.mockReset()
  })

  it('saves an edited note', async () => {
    const user = userEvent.setup()

    render(
      <ExpandedRowNotes
        item={{
          id: 'item-1',
          symbol: 'MSFT',
          note: 'Original note',
        } as any}
      />,
    )

    await user.click(screen.getByRole('button', { name: /edit/i }))
    await user.clear(screen.getByPlaceholderText(/add a note about this symbol/i))
    await user.type(screen.getByPlaceholderText(/add a note about this symbol/i), 'Updated note')
    await user.click(screen.getByRole('button', { name: /save/i }))

    expect(mutate).toHaveBeenCalledWith(
      {
        itemId: 'item-1',
        data: { note: 'Updated note' },
      },
      expect.objectContaining({
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      }),
    )
  })

  it('marks save and cancel actions busy while a note update is in flight', async () => {
    useUpdateWatchlistItemMock.mockReturnValue({
      mutate,
      isPending: true,
    })
    const user = userEvent.setup()

    render(
      <ExpandedRowNotes
        item={{
          id: 'item-1',
          symbol: 'MSFT',
          note: 'Original note',
        } as any}
      />,
    )

    await user.click(screen.getByRole('button', { name: /edit/i }))

    expect(screen.getByRole('button', { name: /cancel/i })).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('button', { name: /save/i })).toHaveAttribute('aria-busy', 'true')
  })
})
