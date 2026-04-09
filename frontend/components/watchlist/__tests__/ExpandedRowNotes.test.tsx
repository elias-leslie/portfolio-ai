import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { WatchlistItem } from '@/lib/api/watchlist'
import { ExpandedRowNotes } from '../ExpandedRowNotes'

function buildItem(overrides: Partial<WatchlistItem> = {}): WatchlistItem {
  return {
    id: 'item-1',
    symbol: 'MSFT',
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
    ...overrides,
  }
}

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

    render(<ExpandedRowNotes item={buildItem({ note: 'Original note' })} />)

    await user.click(screen.getByRole('button', { name: /edit/i }))
    await user.clear(
      screen.getByPlaceholderText(/add a note about this symbol/i),
    )
    await user.type(
      screen.getByPlaceholderText(/add a note about this symbol/i),
      'Updated note',
    )
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

    render(<ExpandedRowNotes item={buildItem({ note: 'Original note' })} />)

    await user.click(screen.getByRole('button', { name: /edit/i }))

    expect(screen.getByRole('button', { name: /cancel/i })).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(screen.getByRole('button', { name: /save/i })).toHaveAttribute(
      'aria-busy',
      'true',
    )
  })
})
