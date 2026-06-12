'use client'

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { HouseholdDocumentCenter } from '../HouseholdDocumentCenter'

const mutate = vi.fn()
const mutateAsync = vi.fn()
const batchMutate = vi.fn()
const batchMutateAsync = vi.fn()
const deleteMutate = vi.fn()
const deleteMutateAsync = vi.fn()
const useUploadHouseholdDocumentMock = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useUploadHouseholdDocument: () =>
    useUploadHouseholdDocumentMock() ?? {
      mutate,
      mutateAsync,
      isPending: false,
    },
  useUploadHouseholdDocuments: () => ({
    mutate: batchMutate,
    mutateAsync: batchMutateAsync,
    isPending: false,
  }),
  useDeleteHouseholdDocument: () => ({
    mutate: deleteMutate,
    mutateAsync: deleteMutateAsync,
    isPending: false,
  }),
}))

describe('HouseholdDocumentCenter', () => {
  beforeEach(() => {
    mutate.mockReset()
    mutateAsync.mockReset()
    batchMutate.mockReset()
    batchMutateAsync.mockReset()
    deleteMutate.mockReset()
    deleteMutateAsync.mockReset()
    useUploadHouseholdDocumentMock.mockReset()
  })

  it('stages a pasted screenshot and uploads it', async () => {
    mutateAsync.mockResolvedValue(undefined)
    render(<HouseholdDocumentCenter documents={[]} />)

    const screenshot = new File(['image-bytes'], 'clipboard.png', {
      type: 'image/png',
    })
    const pasteTarget = screen.getByRole('button', {
      name: /paste, drop, or choose evidence files to upload/i,
    })

    fireEvent.paste(pasteTarget, {
      clipboardData: {
        files: [screenshot],
      },
    })

    expect(screen.getByText(/ready to upload: 1 file/i)).toBeInTheDocument()
    expect(screen.getByText('clipboard.png')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /upload file/i }))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          file: screenshot,
          accountLabel: undefined,
        }),
      )
    })
  })

  it('uploads pasted raw text through the same intake path', async () => {
    mutateAsync.mockResolvedValue(undefined)
    render(<HouseholdDocumentCenter documents={[]} />)

    await userEvent.type(
      screen.getByLabelText(/or paste raw account text/i),
      'CHASE AMAZON CARD\nStatement ending 04/10/2026\nPayment due 05/05/2026',
    )

    fireEvent.click(screen.getByRole('button', { name: /upload text/i }))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          rawText:
            'CHASE AMAZON CARD\nStatement ending 04/10/2026\nPayment due 05/05/2026',
          filename: 'add-anything.txt',
          accountLabel: undefined,
        }),
      )
    })
  })

  it('stages multiple selected files and uploads them together via the batch path', async () => {
    batchMutateAsync.mockResolvedValue([])
    render(<HouseholdDocumentCenter documents={[]} />)

    const january = new File(['jan'], 'january.pdf', {
      type: 'application/pdf',
    })
    const february = new File(['feb'], 'february.pdf', {
      type: 'application/pdf',
    })
    const input = screen.getByLabelText(/^files$/i)

    fireEvent.change(input, {
      target: {
        files: [january, february],
      },
    })

    expect(screen.getByText(/ready to upload: 2 files/i)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /upload files/i }),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /upload files/i }))

    await waitFor(() => {
      expect(batchMutateAsync).toHaveBeenCalledTimes(1)
    })
    const [payloads] = batchMutateAsync.mock.calls[0]
    expect(payloads).toHaveLength(2)
    expect(payloads[0]).toMatchObject({ file: january })
    expect(payloads[1]).toMatchObject({ file: february })
    expect(payloads[0].reviewSessionId).toBeTruthy()
    expect(payloads[0].reviewSessionId).toBe(payloads[1].reviewSessionId)
    expect(mutateAsync).not.toHaveBeenCalled()
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

    expect(
      screen.getByText(/source pending · type pending/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/^staged$/i)).toBeInTheDocument()
    expect(
      screen.getByText(/older document awaiting re-review/i),
    ).toBeInTheDocument()
  })

  it('discards an evidence document after confirmation', async () => {
    const user = userEvent.setup()
    render(
      <HouseholdDocumentCenter
        documents={[
          {
            id: 'doc-discard',
            filename: 'mistake.pdf',
            sourceType: 'other',
            documentType: 'other',
            status: 'staged',
            accountLabel: null,
            fileSizeBytes: 1024,
            contentType: 'application/pdf',
            classificationConfidence: null,
            reviewStatus: null,
            reviewSummary: null,
            reviewConfidence: null,
            statementStart: null,
            statementEnd: null,
            uploadedAt: '2026-05-10T00:00:00Z',
            parsedAt: null,
            metadata: {},
          },
        ]}
      />,
    )

    await user.click(
      screen.getByRole('button', { name: /discard mistake\.pdf/i }),
    )
    await user.click(screen.getByRole('button', { name: /^discard$/i }))

    expect(deleteMutate).toHaveBeenCalledWith(
      'doc-discard',
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    )
  })

  it('clears the staged file queue without uploading', async () => {
    const user = userEvent.setup()
    render(<HouseholdDocumentCenter documents={[]} />)

    const january = new File(['jan'], 'january.pdf', {
      type: 'application/pdf',
    })
    const input = screen.getByLabelText(/^files$/i)

    fireEvent.change(input, {
      target: {
        files: [january],
      },
    })

    expect(screen.getByText(/ready to upload: 1 file/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^clear$/i }))

    expect(
      screen.queryByText(/ready to upload: 1 file/i),
    ).not.toBeInTheDocument()
    expect(mutateAsync).not.toHaveBeenCalled()
  })

  it('reports duplicate files already staged in the queue', () => {
    render(<HouseholdDocumentCenter documents={[]} />)

    const january = new File(['jan'], 'january.pdf', {
      type: 'application/pdf',
    })
    const input = screen.getByLabelText(/^files$/i)

    fireEvent.change(input, {
      target: {
        files: [january],
      },
    })
    fireEvent.change(input, {
      target: {
        files: [january],
      },
    })

    expect(screen.getByText(/skipped 1 duplicate file/i)).toBeInTheDocument()
  })

  it('surfaces intake guidance and document timing metadata', () => {
    render(
      <HouseholdDocumentCenter
        importCenter={{
          headline: 'Import',
          trackedDocuments: 8,
          parsedDocuments: 5,
          suggestedFirstUploads: ['Checking account statement'],
          automations: [],
          supportedDocuments: [],
        }}
        documents={[
          {
            id: 'doc-1',
            filename: 'march.pdf',
            sourceType: 'bank_statement',
            documentType: 'statement',
            status: 'parsed',
            accountLabel: 'Primary Checking',
            fileSizeBytes: 1024,
            contentType: 'application/pdf',
            classificationConfidence: 0.87,
            reviewStatus: 'complete',
            reviewSummary: 'Parsed successfully.',
            reviewConfidence: 0.92,
            statementStart: '2026-03-01',
            statementEnd: '2026-03-31',
            uploadedAt: '2026-03-10T00:00:00Z',
            parsedAt: '2026-03-10T01:00:00Z',
            metadata: {},
          },
        ]}
      />,
    )

    expect(screen.getByText('8')).toBeInTheDocument()
    expect(screen.getByText(/5 parsed so far/i)).toBeInTheDocument()
    expect(
      screen.queryByText('Checking account statement'),
    ).not.toBeInTheDocument()
    expect(
      screen.getByText(/statement window mar 1, 2026 to mar 31, 2026/i),
    ).toBeInTheDocument()
  })

  it('keeps intake focused on upload status without extra workflow copy', () => {
    render(
      <HouseholdDocumentCenter
        documents={[]}
        importCenter={{
          headline: 'Import',
          trackedDocuments: 8,
          parsedDocuments: 5,
          suggestedFirstUploads: ['Checking account statement'],
          automations: [
            'Forward retailer email receipts to intake.',
            'Upload statements only when account sync is stale.',
          ],
          supportedDocuments: [],
        }}
      />,
    )

    expect(screen.getByText(/recent intake/i)).toBeInTheDocument()
    expect(screen.queryByText(/smart intake paths/i)).not.toBeInTheDocument()
    expect(
      screen.queryByText(/forward retailer email receipts to intake/i),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/needed right now/i)).not.toBeInTheDocument()
  })

  it('surfaces focused future-date evidence issues without treating them as applied transactions', () => {
    render(
      <HouseholdDocumentCenter
        documents={[]}
        dateQualityIssues={[
          {
            id: 'future-date-1',
            transactionId: 'txn-1',
            documentId: 'doc-1',
            filename: 'walmart-order.pdf',
            sourceType: 'receipt',
            documentType: 'receipt',
            transactionDate: '2026-09-03',
            uploadedAt: '2026-03-09',
            merchant: 'Walmart',
            description: 'Walmart receipt',
            amount: 164.14,
            accountLabel: 'Visa Credit ****4635',
            confidence: 0.9,
            reason:
              'Extracted transaction date is after today, so Jenny is holding it out of current money calculations.',
            sourceExcerpt: '09/03/2026 Order details - Walmart.com',
          },
        ]}
        focusedReview
      />,
    )

    expect(
      screen.getByText(/1 transaction has a future date/i),
    ).toBeInTheDocument()
    expect(screen.getByText('walmart-order.pdf')).toBeInTheDocument()
    expect(screen.getByText(/extracted 2026-09-03/i)).toBeInTheDocument()
    expect(screen.getByText('$164')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /upload corrected evidence/i }),
    ).toHaveAttribute('href', '#add-evidence-upload')
    expect(
      screen.getByRole('link', { name: /re-upload corrected file/i }),
    ).toHaveAttribute('href', '#add-evidence-upload')
  })

  it('surfaces future-date evidence issues even when the review is not focused', () => {
    render(
      <HouseholdDocumentCenter
        documents={[]}
        dateQualityIssues={[
          {
            id: 'future-date-2',
            transactionId: 'txn-2',
            documentId: 'doc-2',
            filename: 'target-order.pdf',
            sourceType: 'receipt',
            documentType: 'receipt',
            transactionDate: '2026-10-12',
            uploadedAt: '2026-03-09',
            merchant: 'Target',
            description: 'Target receipt',
            amount: 58.2,
            accountLabel: 'Visa Credit ****4635',
            confidence: 0.9,
            reason:
              'Extracted transaction date is after today, so Jenny is holding it out of current money calculations.',
            sourceExcerpt: '10/12/2026 Order details - Target.com',
          },
        ]}
      />,
    )

    expect(
      screen.getByText(/1 transaction has a future date/i),
    ).toBeInTheDocument()
    expect(screen.getByText('target-order.pdf')).toBeInTheDocument()
  })

  it('suppresses the size and mimetype line for synthetic zero-byte documents', () => {
    render(
      <HouseholdDocumentCenter
        documents={[
          {
            id: 'doc-soft-charges',
            filename: 'Phone-entered charges',
            sourceType: 'manual',
            documentType: 'other',
            status: 'parsed',
            accountLabel: null,
            fileSizeBytes: 0,
            contentType: 'application/json',
            classificationConfidence: null,
            reviewStatus: 'complete',
            reviewSummary: null,
            reviewConfidence: 0.95,
            statementStart: null,
            statementEnd: null,
            uploadedAt: '2026-05-10T00:00:00Z',
            parsedAt: '2026-05-10T00:01:00Z',
            metadata: {},
          },
        ]}
      />,
    )

    expect(screen.queryByText('0 B')).not.toBeInTheDocument()
    expect(screen.queryByText('application/json')).not.toBeInTheDocument()
    expect(screen.getByText(/jenny: complete/i)).toBeInTheDocument()
  })

  it('marks upload controls busy while household documents are uploading', () => {
    useUploadHouseholdDocumentMock.mockReturnValue({
      mutate,
      mutateAsync,
      isPending: true,
    })

    render(<HouseholdDocumentCenter documents={[]} />)

    const january = new File(['jan'], 'january.pdf', {
      type: 'application/pdf',
    })
    fireEvent.change(screen.getByLabelText(/^files$/i), {
      target: {
        files: [january],
      },
    })

    expect(screen.getByRole('button', { name: /uploading/i })).toHaveAttribute(
      'aria-busy',
      'true',
    )
    expect(screen.getByRole('button', { name: /^clear$/i })).toHaveAttribute(
      'aria-busy',
      'true',
    )
  })
})
