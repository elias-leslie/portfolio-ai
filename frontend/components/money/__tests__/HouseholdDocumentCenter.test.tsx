'use client'

import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { HouseholdDocumentCenter } from '../HouseholdDocumentCenter'

const mutate = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useUploadHouseholdDocument: () => ({
    mutate,
    isPending: false,
  }),
}))

describe('HouseholdDocumentCenter', () => {
  it('stages a pasted screenshot and uploads it', () => {
    render(<HouseholdDocumentCenter documents={[]} />)

    const screenshot = new File(['image-bytes'], 'clipboard.png', {
      type: 'image/png',
    })
    const pasteTarget = screen.getByRole('button', {
      name: /paste or drop screenshots here/i,
    })

    fireEvent.paste(pasteTarget, {
      clipboardData: {
        files: [screenshot],
      },
    })

    expect(
      screen.getByText((_, element) => element?.textContent === 'Ready to upload: clipboard.png'),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /stage document/i }))

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({
        file: screenshot,
      }),
      expect.any(Object),
    )
  })
})
