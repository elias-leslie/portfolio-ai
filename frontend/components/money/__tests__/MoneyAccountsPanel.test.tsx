'use client'

import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
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
  useUploadHouseholdDocuments: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useDeleteHouseholdDocument: () => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
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
    householdAccountId: 'household-1',
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
    accountMask: 'Z00000001',
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
    deleteMutateAsync.mockResolvedValue(undefined)
  })

  it('renders account rows and uploads evidence bound to the selected account', async () => {
    render(
      <MoneyAccountsPanel
        accounts={[
          {
            ...accounts[0],
            linkedPortfolioAccountName: 'Main Checking Portfolio',
          },
        ]}
        documents={documents}
      />,
    )

    expect(screen.getByText('Balance fresh')).toBeInTheDocument()
    expect(screen.getByText('Activity fresh')).toBeInTheDocument()
    expect(screen.queryByText(/linked to/i)).not.toBeInTheDocument()
    expect(
      screen.queryByText('Main Checking Portfolio'),
    ).not.toBeInTheDocument()

    await userEvent.click(
      screen.getByRole('button', { name: /main checking/i }),
    )

    expect(screen.getByText('Supporting documents')).toBeInTheDocument()
    expect(screen.getByText('checking-april.pdf')).toBeInTheDocument()
    expect(screen.getByText(/selected: main checking/i)).toBeInTheDocument()

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
          householdAccountId: 'household-1',
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
          filename: 'main-checking.txt',
          accountLabel: 'Main Checking',
          householdAccountId: 'household-1',
        }),
      )
    })
  })

  it('keeps account triggers free of nested tooltip buttons and keyboard-operable', async () => {
    const user = userEvent.setup()
    render(<MoneyAccountsPanel accounts={accounts} documents={documents} />)

    const accountTrigger = screen.getByRole('button', {
      name: /main checking/i,
    })

    expect(accountTrigger.querySelector('button')).toBeNull()
    expect(
      screen.queryByRole('button', { name: /coverage: more detail/i }),
    ).not.toBeInTheDocument()

    accountTrigger.focus()
    await user.keyboard('{Enter}')

    expect(screen.getByText('Supporting documents')).toBeInTheDocument()
  })

  it('does not show review-only account controls as account-page alerts', () => {
    render(
      <MoneyAccountsPanel
        accounts={accounts}
        documents={documents}
        accountControl={{
          status: 'review',
          summary:
            '1 account control review item found; totals are not double-counting it.',
          issueCount: 1,
          blockingIssueCount: 0,
          checkedAt: '2026-04-11T00:00:00Z',
          issues: [
            {
              id: 'duplicate_source_alias:cash',
              code: 'duplicate_source_alias',
              severity: 'medium',
              title: 'Duplicate source aliases collapsed',
              detail:
                'Cash Management is represented by two matching source rows.',
              householdAccountId: 'cash',
              accountLabel: 'Cash Management',
              source: 'snaptrade',
              sourceAccountIds: ['source-1', 'source-2'],
              affectsTotals: false,
            },
          ],
        }}
      />,
    )

    expect(
      screen.queryByText('Totals Need Reconciliation'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText('Duplicate source aliases collapsed'),
    ).not.toBeInTheDocument()
  })

  it('flags totals-blocking account control issues with a Blocked badge', () => {
    render(
      <MoneyAccountsPanel
        accounts={accounts}
        documents={documents}
        accountControl={{
          status: 'blocked',
          summary: 'Totals are blocked by 1 reconciliation issue.',
          issueCount: 1,
          blockingIssueCount: 1,
          checkedAt: '2026-04-11T00:00:00Z',
          issues: [
            {
              id: 'overlapping_sources:cash',
              code: 'overlapping_sources',
              severity: 'high',
              title: 'Overlapping balance sources',
              detail: 'Two sources currently report the same checking account.',
              householdAccountId: 'cash',
              accountLabel: 'Main Checking',
              source: 'plaid',
              sourceAccountIds: ['source-1'],
              affectsTotals: true,
            },
          ],
        }}
      />,
    )

    expect(screen.getByText('Totals Need Reconciliation')).toBeInTheDocument()
    expect(screen.getByText('Blocked')).toBeInTheDocument()
    expect(screen.getByText('Overlapping balance sources')).toBeInTheDocument()
  })

  it('renders tracked accounts above the discovered-account suggestions', () => {
    render(
      <MoneyAccountsPanel
        accounts={accounts}
        documents={documents}
        discoveredAccounts={discoveredAccounts}
      />,
    )

    const tracked = screen.getByText('Main Checking')
    const discovered = screen.getByText(/possible accounts jenny found/i)
    expect(
      tracked.compareDocumentPosition(discovered) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('creates an account from the add account dialog', async () => {
    const user = userEvent.setup()
    render(<MoneyAccountsPanel accounts={accounts} documents={documents} />)

    await user.click(screen.getByRole('button', { name: /add account/i }))
    await user.type(
      screen.getByLabelText(/account label/i),
      'Emergency Savings',
    )
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

  it('prefills an account from a discovered account hint', async () => {
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

    await user.click(
      screen.getByRole('button', { name: /create tracked row/i }),
    )

    expect(screen.getByLabelText(/account label/i)).toHaveValue(
      'Wells Fargo · …4421',
    )
    expect(screen.getByLabelText(/institution/i)).toHaveValue('Wells Fargo')
    expect(screen.getByLabelText(/account mask/i)).toHaveValue('4421')
    expect(screen.getByText('Confirm account')).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /save account details/i }),
    )

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

  it('edits and renames an account', async () => {
    const user = userEvent.setup()
    render(<MoneyAccountsPanel accounts={accounts} documents={documents} />)

    await user.click(screen.getByRole('button', { name: /main checking/i }))
    await user.click(screen.getByRole('button', { name: /edit/i }))
    const dialog = screen.getByRole('dialog')
    const labelInput = within(dialog).getByLabelText(/account label/i)
    await user.clear(labelInput)
    await user.type(labelInput, 'Household Checking')
    await user.click(
      within(dialog).getByRole('button', { name: /save account details/i }),
    )

    await waitFor(() => {
      expect(updateMutateAsync).toHaveBeenCalledWith({
        accountId: 'tracked-1',
        payload: expect.objectContaining({
          label: 'Household Checking',
        }),
      })
    })
  })

  it('hides backend identity fields when editing an evidence-backed account', async () => {
    const user = userEvent.setup()
    render(<MoneyAccountsPanel accounts={accounts} documents={documents} />)

    await user.click(screen.getByRole('button', { name: /main checking/i }))
    await user.click(screen.getByRole('button', { name: /edit/i }))

    const dialog = screen.getByRole('dialog')
    expect(await within(dialog).findByText('Edit account')).toBeInTheDocument()
    expect(
      within(dialog).getByText(/update the account display details/i),
    ).toBeInTheDocument()
    expect(
      within(dialog).queryByLabelText(/asset group/i),
    ).not.toBeInTheDocument()
    expect(
      within(dialog).queryByLabelText(/account type/i),
    ).not.toBeInTheDocument()
    expect(
      within(dialog).queryByLabelText(/institution/i),
    ).not.toBeInTheDocument()
    expect(
      within(dialog).queryByLabelText(/account mask/i),
    ).not.toBeInTheDocument()
    expect(within(dialog).getByLabelText(/owner/i)).toBeEnabled()
    expect(
      within(dialog).getByRole('button', { name: /save account details/i }),
    ).toBeInTheDocument()
  })

  it('keeps backend identity fields hidden even if account temporarily reports zero evidence', async () => {
    const user = userEvent.setup()
    render(
      <MoneyAccountsPanel
        accounts={[
          {
            ...accounts[0],
            evidenceCount: 0,
            documentIds: [],
            latestDocumentId: null,
            lastEvidenceAt: null,
          },
        ]}
        documents={documents}
      />,
    )

    await user.click(screen.getByRole('button', { name: /main checking/i }))
    await user.click(screen.getByRole('button', { name: /edit/i }))

    const dialog = screen.getByRole('dialog')
    expect(
      within(dialog).queryByLabelText(/institution/i),
    ).not.toBeInTheDocument()
    expect(
      within(dialog).queryByLabelText(/account mask/i),
    ).not.toBeInTheDocument()
    expect(within(dialog).getByLabelText(/owner/i)).toBeEnabled()
  })

  it('archives account from the row dialog', async () => {
    const user = userEvent.setup()
    render(<MoneyAccountsPanel accounts={accounts} documents={documents} />)

    await user.click(screen.getByRole('button', { name: /main checking/i }))
    await user.click(screen.getByRole('button', { name: /archive/i }))
    await user.click(screen.getByRole('button', { name: /archive account/i }))

    await waitFor(() => {
      expect(deleteMutateAsync).toHaveBeenCalledWith('household-1')
    })
  })

  it('archives evidence-only accounts after display settings are gone', async () => {
    const user = userEvent.setup()
    render(
      <MoneyAccountsPanel
        accounts={[
          {
            ...accounts[0],
            accountOrigin: 'evidence',
            trackedAccountId: null,
          },
        ]}
        documents={documents}
      />,
    )

    await user.click(screen.getByRole('button', { name: /main checking/i }))
    await user.click(screen.getByRole('button', { name: /archive/i }))
    await user.click(screen.getByRole('button', { name: /archive account/i }))

    await waitFor(() => {
      expect(deleteMutateAsync).toHaveBeenCalledWith('household-1')
    })
  })

  it('edits an evidence-backed account by anchoring customization to the official account id', async () => {
    const user = userEvent.setup()
    render(
      <MoneyAccountsPanel
        accounts={evidenceOnlyAccounts}
        documents={documents}
      />,
    )

    await user.click(
      screen.getByRole('button', { name: /cash management \(joint wros\)/i }),
    )
    await user.click(screen.getByRole('button', { name: /edit/i }))

    expect(screen.getByLabelText(/account label/i)).toHaveValue(
      'Cash Management (Joint WROS)',
    )
    expect(await screen.findByText('Edit account')).toBeInTheDocument()
    const dialog = screen.getByRole('dialog')
    expect(
      within(dialog).queryByLabelText(/account mask/i),
    ).not.toBeInTheDocument()

    const labelInput = within(dialog).getByLabelText(/account label/i)
    await user.clear(labelInput)
    await user.type(labelInput, 'Main Cash Management')
    await user.click(
      within(dialog).getByRole('button', { name: /save account details/i }),
    )

    await waitFor(() => {
      expect(createMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          householdAccountId: 'household-1',
          label: 'Main Cash Management',
          accountMask: 'Z00000001',
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

    expect(screen.getByText('Supporting documents')).toBeInTheDocument()
    expect(screen.getByText(/selected: main checking/i)).toBeInTheDocument()
  })

  it('shows exact stale balance and transaction evidence dates by account', async () => {
    const user = userEvent.setup()
    render(
      <MoneyAccountsPanel
        accounts={[
          {
            ...accounts[0],
            balanceFreshnessStatus: 'stale',
            balanceFreshnessLabel: 'Stale',
            transactionFreshnessStatus: 'stale',
            transactionFreshnessLabel: 'Stale',
            freshnessStatus: 'stale',
            freshnessLabel: 'Stale',
            lastBalanceAt: '2026-04-11',
            daysSinceBalance: 13,
            lastTransactionAt: '2026-04-14',
            daysSinceTransaction: 10,
          },
        ]}
        documents={documents}
      />,
    )

    await user.click(screen.getByRole('button', { name: /main checking/i }))

    expect(
      screen.getByText(
        (_, element) =>
          element?.textContent === 'Balance Stale · Apr 11, 2026 (13d old)',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        (_, element) =>
          element?.textContent ===
          'Transactions Stale · Apr 14, 2026 (10d old)',
      ),
    ).toBeInTheDocument()
  })

  it('offers authoritative remediation for a stale document-only account', async () => {
    const user = userEvent.setup()
    render(
      <MoneyAccountsPanel
        accounts={[
          {
            ...accounts[0],
            accountOrigin: 'evidence',
            valuationSource: 'evidence',
            linkedPortfolioAccountId: null,
            balanceFreshnessStatus: 'stale',
            balanceFreshnessLabel: 'Stale',
            freshnessStatus: 'stale',
            freshnessLabel: 'Stale',
            gapFlags: [
              {
                code: 'stale_balance',
                severity: 'high',
                title: 'Stale balance',
                detail: 'The last document value is no longer current.',
              },
            ],
          },
        ]}
        documents={documents}
      />,
    )

    await user.click(screen.getByRole('button', { name: /main checking/i }))

    expect(screen.getByText('Last known document value')).toBeInTheDocument()
    expect(
      screen.getByText(/it cannot refresh automatically/i),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /upload newer evidence/i }),
    ).toHaveAttribute('href', '#account-evidence-upload-account-1')
    expect(
      screen.getByRole('button', { name: /archive closed account/i }),
    ).toBeInTheDocument()
  })
})
