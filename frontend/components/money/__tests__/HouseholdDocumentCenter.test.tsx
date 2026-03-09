'use client'

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { HouseholdDocumentCenter } from '../HouseholdDocumentCenter'

const mutate = vi.fn()
const mutateAsync = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useUploadHouseholdDocument: () => ({
    mutate,
    mutateAsync,
    isPending: false,
  }),
}))

describe('HouseholdDocumentCenter', () => {
  beforeEach(() => {
    mutate.mockReset()
    mutateAsync.mockReset()
  })

  it('stages a pasted screenshot and uploads it', async () => {
    mutateAsync.mockResolvedValue(undefined)
    render(<HouseholdDocumentCenter documents={[]} />)

    const screenshot = new File(['image-bytes'], 'clipboard.png', {
      type: 'image/png',
    })
    const pasteTarget = screen.getByRole('button', {
      name: /paste or drop screenshots or files here/i,
    })

    fireEvent.paste(pasteTarget, {
      clipboardData: {
        files: [screenshot],
      },
    })

    expect(screen.getByText(/ready to upload: 1 file/i)).toBeInTheDocument()
    expect(screen.getByText('clipboard.png')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /stage document/i }))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          file: screenshot,
        }),
      )
    })
  })

  it('stages multiple selected files and uploads them together', async () => {
    mutateAsync.mockResolvedValue(undefined)
    render(<HouseholdDocumentCenter documents={[]} />)

    const january = new File(['jan'], 'january.pdf', { type: 'application/pdf' })
    const february = new File(['feb'], 'february.pdf', { type: 'application/pdf' })
    const input = screen.getByLabelText(/file/i)

    fireEvent.change(input, {
      target: {
        files: [january, february],
      },
    })

    expect(screen.getByText(/ready to upload: 2 files/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /stage documents/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /stage documents/i }))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledTimes(2)
      expect(mutateAsync).toHaveBeenNthCalledWith(
        1,
        expect.objectContaining({ file: january }),
      )
      expect(mutateAsync).toHaveBeenNthCalledWith(
        2,
        expect.objectContaining({ file: february }),
      )
    })
  })

  it('renders documents with missing classification fields without crashing', () => {
    render(
      <HouseholdDocumentCenter
        documents={[
          {
            id: 'doc-1',
            filename: 'legacy-upload.pdf',
            sourceType: null,
            documentType: null,
            status: null,
            accountLabel: null,
            fileSizeBytes: 1024,
            contentType: 'application/pdf',
            classificationConfidence: null,
            reviewStatus: null,
            reviewSummary: 'Older document awaiting re-review.',
            reviewConfidence: null,
            statementStart: null,
            statementEnd: null,
            uploadedAt: '2026-03-09T00:00:00Z',
            parsedAt: null,
            metadata: {},
          },
        ]}
      />,
    )

    expect(screen.getByText(/source pending · type pending/i)).toBeInTheDocument()
    expect(screen.getByText(/^staged$/i)).toBeInTheDocument()
    expect(screen.getByText(/older document awaiting re-review/i)).toBeInTheDocument()
  })
})
