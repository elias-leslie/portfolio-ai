import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ConfirmActionDialog } from '../ConfirmActionDialog'

describe('ConfirmActionDialog', () => {
  it('shows the thrown error without closing the dialog', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    const onConfirm = vi.fn().mockRejectedValue(new Error('Delete failed'))

    render(
      <ConfirmActionDialog
        open
        onOpenChange={onOpenChange}
        title="Delete position"
        onConfirm={onConfirm}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Continue' }))

    await waitFor(() => {
      expect(screen.getByText('Action failed.')).toBeInTheDocument()
      expect(screen.getByText('Delete failed')).toBeInTheDocument()
    })
    expect(onOpenChange).not.toHaveBeenCalledWith(false)
  })

  it('clears the inline error after the dialog closes', async () => {
    const { rerender } = render(
      <ConfirmActionDialog
        open
        onOpenChange={vi.fn()}
        title="Delete position"
        onConfirm={vi.fn().mockRejectedValue(new Error('Delete failed'))}
      />,
    )

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    await screen.findByText('Delete failed')

    rerender(
      <ConfirmActionDialog
        open={false}
        onOpenChange={vi.fn()}
        title="Delete position"
        onConfirm={vi.fn()}
      />,
    )

    rerender(
      <ConfirmActionDialog
        open
        onOpenChange={vi.fn()}
        title="Delete position"
        onConfirm={vi.fn()}
      />,
    )

    expect(screen.queryByText('Delete failed')).not.toBeInTheDocument()
  })
})
