import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MoneyLedgerPanel } from '../MoneyLedgerPanel'

const useHouseholdLedgerMock = vi.hoisted(() => vi.fn())

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdLedger: useHouseholdLedgerMock,
}))

const PAGE_SIZE = 50

function buildEntry(index: number, overrides = {}) {
  const padded = String(index).padStart(3, '0')
  return {
    id: `txn-${padded}`,
    kind: 'transaction',
    flowType: 'expense',
    householdAccountId: `account-${padded}`,
    accountLabel: `Checking ${index % 3}`,
    date: `2026-04-${String((index % 28) + 1).padStart(2, '0')}T00:00:00+00:00`,
    postedDate: `2026-04-${String((index % 28) + 1).padStart(2, '0')}T00:00:00+00:00`,
    merchant: `Merchant ${padded}`,
    description: `Merchant ${padded} purchase`,
    amount: 10 + index,
    currency: 'USD',
    category: 'groceries',
    essentiality: 'need',
    originalCategory: 'GENERAL_MERCHANDISE',
    categorizationSource: 'plaid',
    categoryUpdatedBy: null,
    categoryUpdatedAt: null,
    datasetType: null,
    externalRowId: `external-${padded}`,
    pending: false,
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

// The server now owns filtering/sorting/paging, so the mock just returns a page
// plus the summary counts the panel renders.
function mockLedgerPage(
  pageEntries: ReturnType<typeof buildEntry>[],
  overrides: Record<string, unknown> = {},
) {
  useHouseholdLedgerMock.mockReturnValue({
    data: {
      generatedAt: '2026-04-24T00:00:00Z',
      timeframeKey: 'all',
      timeframeLabel: 'All dates',
      startDate: null,
      endDate: null,
      transactionCount: 75,
      importRowCount: 0,
      totalEntryCount: 75,
      filteredCount: 75,
      includedCount: 75,
      excludedCount: 0,
      offset: 0,
      limit: PAGE_SIZE,
      returnedCount: pageEntries.length,
      accountOptions: ['Checking 0', 'Checking 1', 'Checking 2'],
      debitTotal: 0,
      creditTotal: 0,
      entries: pageEntries,
      ...overrides,
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

function lastLedgerParams() {
  return useHouseholdLedgerMock.mock.calls.at(-1)?.[0] ?? {}
}

describe('MoneyLedgerPanel', () => {
  beforeEach(() => {
    useHouseholdLedgerMock.mockReset()
  })

  it('renders the returned page and server counts and hides audit internals', () => {
    mockLedgerPage(
      Array.from({ length: PAGE_SIZE }, (_, i) => buildEntry(i + 1)),
    )

    render(<MoneyLedgerPanel />)

    expect(ledgerRows()).toHaveLength(PAGE_SIZE)
    expect(screen.getByText('Showing 1-50 of 75')).toBeInTheDocument()
    expect(screen.queryByText(/statement-\d+\.pdf/)).not.toBeInTheDocument()
    expect(screen.queryByText(/hash-\d+/)).not.toBeInTheDocument()
  })

  it('requests a bounded page from the server (no 50000 fetch)', () => {
    mockLedgerPage(
      Array.from({ length: PAGE_SIZE }, (_, i) => buildEntry(i + 1)),
    )

    render(<MoneyLedgerPanel />)

    expect(lastLedgerParams().limit).toBe(PAGE_SIZE)
    expect(lastLedgerParams().offset).toBe(0)
  })

  it('asks the server for the next page by offset', async () => {
    const user = userEvent.setup()
    mockLedgerPage(
      Array.from({ length: PAGE_SIZE }, (_, i) => buildEntry(i + 1)),
    )

    render(<MoneyLedgerPanel />)

    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(lastLedgerParams().offset).toBe(PAGE_SIZE)
  })

  it('passes the search term to the server', async () => {
    const user = userEvent.setup()
    mockLedgerPage([buildEntry(72)])

    render(<MoneyLedgerPanel />)

    await user.type(
      screen.getByLabelText('Search ledger rows'),
      'statement-072',
    )

    await waitFor(() => {
      expect(lastLedgerParams().search).toBe('statement-072')
    })
  })

  it('requests a merchant sort from the server', async () => {
    const user = userEvent.setup()
    mockLedgerPage([buildEntry(1)])

    render(<MoneyLedgerPanel />)

    await user.click(screen.getByRole('button', { name: 'Merchant' }))

    expect(lastLedgerParams().sort).toBe('detail')
  })

  it('shows pending and provenance only through row audit detail', async () => {
    const user = userEvent.setup()
    mockLedgerPage([
      buildEntry(1, {
        pending: true,
        categorizationSource: 'manual_rule',
        sourceDocumentFilename: 'private-checking-april.pdf',
        rowHash: 'private-row-hash-abcdef123456',
      }),
    ])

    render(<MoneyLedgerPanel />)

    // Pending is visible inline; provenance internals stay behind audit.
    expect(screen.getByText('Pending')).toBeInTheDocument()
    expect(
      screen.queryByText('private-checking-april.pdf'),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Audit' }))

    expect(screen.getByText('Categorized by')).toBeInTheDocument()
    expect(screen.getByText('Manual rule')).toBeInTheDocument()
    expect(screen.getByText('private-checking-april.pdf')).toBeInTheDocument()
  })
})
