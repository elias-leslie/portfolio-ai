import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MoneyLedgerPanel } from '../MoneyLedgerPanel'

const useHouseholdLedgerMock = vi.hoisted(() => vi.fn())

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdLedger: useHouseholdLedgerMock,
}))

function buildEntry(index: number, overrides = {}) {
  const padded = String(index).padStart(3, '0')
  return {
    id: `txn-${padded}`,
    kind: 'transaction',
    flowType: 'expense',
    householdAccountId: `account-${padded}`,
    accountLabel: `Checking ${index % 3}`,
    date: `2026-04-${String((index % 28) + 1).padStart(2, '0')}`,
    postedDate: `2026-04-${String((index % 28) + 1).padStart(2, '0')}`,
    merchant: `Merchant ${padded}`,
    description: `Merchant ${padded} purchase`,
    amount: 10 + index,
    currency: 'USD',
    category: 'groceries',
    essentiality: 'need',
    datasetType: null,
    externalRowId: `external-${padded}`,
    rowHash: `hash-${padded}-abcdef1234567890`,
    sourceDocumentId: `doc-${padded}`,
    sourceDocumentFilename: `statement-${padded}.pdf`,
    sourceType: 'bank',
    documentType: 'statement',
    balanceAfter: 1000 - index,
    uploadedAt: '2026-04-20T00:00:00Z',
    includedInSpend: true,
    exclusionReason: null,
    ...overrides,
  }
}

function mockLedger(entries: ReturnType<typeof buildEntry>[]) {
  useHouseholdLedgerMock.mockReturnValue({
    data: {
      generatedAt: '2026-04-24T00:00:00Z',
      timeframeKey: 'all',
      timeframeLabel: 'All dates',
      startDate: null,
      endDate: null,
      transactionCount: entries.length,
      importRowCount: 0,
      totalEntryCount: entries.length,
      debitTotal: 0,
      creditTotal: 0,
      entries,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    isFetching: false,
  })
}

function ledgerRows() {
  return document.querySelectorAll('[data-ledger-row="entry"]')
}

describe('MoneyLedgerPanel', () => {
  beforeEach(() => {
    useHouseholdLedgerMock.mockReset()
  })

  it('bounds the default rendered rows and hides audit internals', () => {
    mockLedger(Array.from({ length: 75 }, (_, index) => buildEntry(index + 1)))

    render(<MoneyLedgerPanel />)

    expect(ledgerRows()).toHaveLength(50)
    expect(screen.getByText('Showing 1-50 of 75')).toBeInTheDocument()
    expect(screen.queryByText(/statement-\d+\.pdf/)).not.toBeInTheDocument()
    expect(screen.queryByText(/hash-\d+/)).not.toBeInTheDocument()
  })

  it('pages through large result sets without rendering every row', async () => {
    const user = userEvent.setup()
    mockLedger(Array.from({ length: 75 }, (_, index) => buildEntry(index + 1)))

    render(<MoneyLedgerPanel />)

    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByText('Showing 51-75 of 75')).toBeInTheDocument()
    expect(ledgerRows()).toHaveLength(25)
  })

  it('keeps hidden provenance searchable without exposing it by default', async () => {
    const user = userEvent.setup()
    mockLedger(Array.from({ length: 75 }, (_, index) => buildEntry(index + 1)))

    render(<MoneyLedgerPanel />)

    await user.type(
      screen.getByLabelText('Search ledger rows'),
      'statement-072',
    )

    await waitFor(() => {
      expect(ledgerRows()).toHaveLength(1)
    })
    expect(screen.getByText('Merchant 072')).toBeInTheDocument()
    expect(screen.queryByText('statement-072.pdf')).not.toBeInTheDocument()
  })

  it('sorts visible rows by merchant', async () => {
    const user = userEvent.setup()
    mockLedger([
      buildEntry(1, {
        merchant: 'Zulu Market',
        description: 'Zulu Market purchase',
        postedDate: '2026-04-24',
      }),
      buildEntry(2, {
        merchant: 'Alpha Cafe',
        description: 'Alpha Cafe purchase',
        postedDate: '2026-04-23',
      }),
    ])

    render(<MoneyLedgerPanel />)

    expect(ledgerRows()[0]).toHaveTextContent('Zulu Market')

    await user.click(screen.getByRole('button', { name: 'Merchant' }))

    expect(ledgerRows()[0]).toHaveTextContent('Alpha Cafe')
  })

  it('reveals source filenames and hashes only through row audit detail', async () => {
    const user = userEvent.setup()
    mockLedger([
      buildEntry(1, {
        sourceDocumentFilename: 'private-checking-april.pdf',
        rowHash: 'private-row-hash-abcdef123456',
      }),
    ])

    render(<MoneyLedgerPanel />)

    expect(
      screen.queryByText('private-checking-april.pdf'),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByText('private-row-hash-abcdef123456'),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Audit' }))

    expect(screen.getByText('Source file')).toBeInTheDocument()
    expect(screen.getByText('private-checking-april.pdf')).toBeInTheDocument()
    expect(screen.getByText('Row hash')).toBeInTheDocument()
    expect(
      screen.getByText('private-row-hash-abcdef123456'),
    ).toBeInTheDocument()
  })
})
