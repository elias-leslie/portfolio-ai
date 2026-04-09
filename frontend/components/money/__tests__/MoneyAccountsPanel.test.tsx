'use client'

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MoneyAccountsPanel } from '../MoneyAccountsPanel'

const uploadMutateAsync = vi.fn()
const createMutateAsync = vi.fn()
const updateMutateAsync = vi.fn()
const deleteMutateAsync = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useUploadHouseholdDocument: () => ({
    mutateAsync: uploadMutateAsync,
    isPending: false,
  }),
  useCreateHouseholdTrackedAccount: () => ({
    mutateAsync: createMutateAsync,
    isPending: false,
  }),
  useUpdateHouseholdTrackedAccount: () => ({
    mutateAsync: updateMutateAsync,
    isPending: false,
  }),
  useDeleteHouseholdTrackedAccount: () => ({
    mutateAsync: deleteMutateAsync,
    isPending: false,
  }),
}))

const accounts = [
  {
    id: 'account-1',
    label: 'Main Checking',
    assetGroup: 'cash',
    accountType: 'checking',
    sourceType: 'bank',
    institutionName: 'Wells Fargo',
    ownerName: null,
    accountMask: '4421',
    notes: 'Primary bills account',
    currency: 'USD',
    currentValue: 25057,
    balance: 25057,
    holdingsValue: null,
    cashBalance: 25057,
    evidenceCount: 1,
    documentIds: ['doc-1'],
    latestDocumentId: 'doc-1',
    sourceTypes: ['bank'],
    linkedPortfolioAccountId: null,
    linkedPortfolioAccountName: null,
    trackedAccountId: 'tracked-1',
    accountOrigin: 'tracked',
    lastEvidenceAt: '2026-04-07T00:00:00Z',
    daysSinceEvidence: 2,
    freshnessStatus: 'fresh',
    freshnessLabel: 'Fresh',
    matchStatus: 'linked',
    matchConfidence: 0.94,
    gapFlags: [
      {
        code: 'thin_evidence',
        severity: 'low',
        title: 'Thin evidence',
        detail: 'Only one document backs this account right now.',
      },
    ],
  },
]

const documents = [
  {
    id: 'doc-1',
    filename: 'checking-april.pdf',
    sourceType: 'bank',
    documentType: 'statement',
    status: 'parsed',
    accountLabel: 'Main Checking',
    fileSizeBytes: 1024,
    contentType: 'application/pdf',
    classificationConfidence: 0.9,
    reviewStatus: 'complete',
    reviewSummary: 'Reviewed',
    reviewConfidence: 0.92,
    statementStart: '2026-04-01',
    statementEnd: '2026-04-30',
    uploadedAt: '2026-04-07T00:00:00Z',
    parsedAt: '2026-04-07T00:05:00Z',
    metadata: {},
  },
]

describe('MoneyAccountsPanel', () => {
  beforeEach(() => {
    uploadMutateAsync.mockReset()
    createMutateAsync.mockReset()
    updateMutateAsync.mockReset()
    deleteMutateAsync.mockReset()
    createMutateAsync.mockResolvedValue(undefined)
    updateMutateAsync.mockResolvedValue(undefined)
    uploadMutateAsync.mockResolvedValue(undefined)
  })

  it('renders account rows and uploads evidence with an account hint', async () => {
    render(<MoneyAccountsPanel accounts={accounts} documents={documents} />)

    await userEvent.click(screen.getByRole('button', { name: /main checking/i }))

    expect(screen.getByText('Supporting documents')).toBeInTheDocument()
    expect(screen.getByText('checking-april.pdf')).toBeInTheDocument()
    expect(
      screen.getByText(/hint: main checking/i),
    ).toBeInTheDocument()

    const input = screen.getByLabelText('Files')
    const file = new File(['pdf'], 'may.pdf', { type: 'application/pdf' })
    fireEvent.change(input, {
      target: {
        files: [file],
      },
    })

    await userEvent.click(screen.getByRole('button', { name: /upload file/i }))

    await waitFor(() => {
      expect(uploadMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          file,
          accountLabel: 'Main Checking',
        }),
      )
    })
  })

  it('creates a tracked account from the add account dialog', async () => {
    const user = userEvent.setup()
    render(<MoneyAccountsPanel accounts={accounts} documents={documents} />)

    await user.click(screen.getByRole('button', { name: /add account/i }))
    await user.type(screen.getByLabelText(/account label/i), 'Emergency Savings')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    await waitFor(() => {
      expect(createMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          label: 'Emergency Savings',
          assetGroup: 'cash',
          accountType: 'checking',
          sourceType: 'bank',
        }),
      )
    })
  })
})
