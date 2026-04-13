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
    matchKey: null,
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
    moneyRole: 'spend_driver',
    lastEvidenceAt: '2026-04-07T00:00:00Z',
    daysSinceEvidence: 2,
    lastBalanceAt: '2026-04-07T00:00:00Z',
    daysSinceBalance: 2,
    balanceFreshnessStatus: 'fresh',
    balanceFreshnessLabel: 'Fresh',
    lastTransactionAt: '2026-04-06T00:00:00Z',
    daysSinceTransaction: 3,
    transactionFreshnessStatus: 'fresh',
    transactionFreshnessLabel: 'Fresh',
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

const discoveredAccounts = [
  {
    key: 'discover-wells-4421',
    institution: 'Wells Fargo',
    partialAccount: '4421',
    suggestedLabel: 'Wells Fargo · …4421',
    assetGroup: 'cash',
    accountType: 'checking',
    sourceType: 'bank',
    confidence: 0.88,
    occurrenceCount: 2,
    sampleDescription: 'ONLINE TRANSFER FROM WELLS FARGO 4421',
    detail:
      'Statement activity references a likely Wells Fargo checking account ending in 4421. Confirm it if this is a real household account.',
  },
]

const evidenceOnlyAccounts = [
  {
    ...accounts[0],
    id: 'account-2',
    label: 'Cash Management (Joint WROS)',
    accountMask: 'Z38367298',
    trackedAccountId: null,
    accountOrigin: 'evidence',
    linkedPortfolioAccountId: 'portfolio-1',
    linkedPortfolioAccountName: 'Cash Management (Joint WROS)',
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

  it('uploads pasted raw text with the selected account as a hint', async () => {
    const user = userEvent.setup()
    render(<MoneyAccountsPanel accounts={accounts} documents={documents} />)

    await user.click(screen.getByRole('button', { name: /main checking/i }))
    await user.type(
      screen.getByLabelText(/or paste raw account text/i),
      'Available balance $25,057\nPosted transaction 04/06/2026\nVendor: Amazon',
    )

    await user.click(screen.getByRole('button', { name: /upload text/i }))

    await waitFor(() => {
        expect(uploadMutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({
            rawText:
              'Available balance $25,057\nPosted transaction 04/06/2026\nVendor: Amazon',
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

  it('prefills a tracked account from a discovered account hint', async () => {
    const user = userEvent.setup()
    render(
      <MoneyAccountsPanel
        accounts={accounts}
        documents={documents}
        discoveredAccounts={discoveredAccounts}
        focus="discovered"
      />,
    )

    expect(
      screen.getByText(/possible accounts jenny found/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/today sent you here because jenny found account hints/i),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /create tracked row/i }))

    expect(screen.getByLabelText(/account label/i)).toHaveValue(
      'Wells Fargo · …4421',
    )
    expect(screen.getByLabelText(/institution/i)).toHaveValue('Wells Fargo')
    expect(screen.getByLabelText(/account mask/i)).toHaveValue('4421')
    expect(screen.getByText('Track account')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /save account details/i }))

    await waitFor(() => {
      expect(createMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          label: 'Wells Fargo · …4421',
          institutionName: 'Wells Fargo',
          accountMask: '4421',
          assetGroup: 'cash',
          accountType: 'checking',
          sourceType: 'bank',
        }),
      )
    })
  })

  it('edits and renames a tracked account', async () => {
    const user = userEvent.setup()
    render(<MoneyAccountsPanel accounts={accounts} documents={documents} />)

    await user.click(screen.getByRole('button', { name: /main checking/i }))
    await user.click(screen.getByRole('button', { name: /edit/i }))
    const labelInput = screen.getByLabelText(/account label/i)
    await user.clear(labelInput)
    await user.type(labelInput, 'Household Checking')
    await user.click(screen.getByRole('button', { name: /save account/i }))

    await waitFor(() => {
      expect(updateMutateAsync).toHaveBeenCalledWith({
        accountId: 'tracked-1',
        payload: expect.objectContaining({
          label: 'Household Checking',
        }),
      })
    })
  })

  it('locks identity fields when editing an evidence-linked tracked account', async () => {
    const user = userEvent.setup()
    render(<MoneyAccountsPanel accounts={accounts} documents={documents} />)

    await user.click(screen.getByRole('button', { name: /main checking/i }))
    await user.click(screen.getByRole('button', { name: /edit/i }))

    expect(screen.getByText('Edit account label')).toBeInTheDocument()
    expect(
      screen.getByText(/identity fields stay tied to linked evidence/i),
    ).toBeInTheDocument()
    expect(screen.getByLabelText(/institution/i)).toBeDisabled()
    expect(screen.getByLabelText(/account mask/i)).toBeDisabled()
    expect(screen.getByLabelText(/owner/i)).toBeDisabled()
    expect(screen.getByRole('button', { name: /save label/i })).toBeInTheDocument()
  })

  it('deletes a tracked account from the row dialog', async () => {
    const user = userEvent.setup()
    render(<MoneyAccountsPanel accounts={accounts} documents={documents} />)

    await user.click(screen.getByRole('button', { name: /main checking/i }))
    await user.click(screen.getByRole('button', { name: /delete/i }))
    await user.click(screen.getByRole('button', { name: /delete account/i }))

    await waitFor(() => {
      expect(deleteMutateAsync).toHaveBeenCalledWith('tracked-1')
    })
  })

  it('creates a tracked row from an evidence-backed account so name can be customized', async () => {
    const user = userEvent.setup()
    render(<MoneyAccountsPanel accounts={evidenceOnlyAccounts} documents={documents} />)

    await user.click(screen.getByRole('button', { name: /cash management \(joint wros\)/i }))
    await user.click(screen.getByRole('button', { name: /track \/ rename/i }))

    expect(screen.getByLabelText(/account label/i)).toHaveValue(
      'Cash Management (Joint WROS)',
    )
    expect(screen.getByLabelText(/account mask/i)).toHaveValue('Z38367298')
    expect(screen.getByText('Track account')).toBeInTheDocument()

    const labelInput = screen.getByLabelText(/account label/i)
    await user.clear(labelInput)
    await user.type(labelInput, 'Main Cash Management')
    await user.click(screen.getByRole('button', { name: /save account details/i }))

    await waitFor(() => {
      expect(createMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          label: 'Main Cash Management',
          accountMask: 'Z38367298',
          sourceType: 'bank',
        }),
      )
    })
  })

  it('opens and highlights the first account needing coverage when focused from Today', () => {
    render(
      <MoneyAccountsPanel
        accounts={accounts}
        documents={documents}
        discoveredAccounts={[]}
        focus="coverage"
      />,
    )

    expect(
      screen.getByText(/today sent you here to confirm account coverage/i),
    ).toBeInTheDocument()
    expect(screen.getByText('Supporting documents')).toBeInTheDocument()
    expect(screen.getByText(/hint: main checking/i)).toBeInTheDocument()
  })
})
