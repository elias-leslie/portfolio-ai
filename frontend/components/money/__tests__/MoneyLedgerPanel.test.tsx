import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MoneyLedgerPanel } from '../MoneyLedgerPanel'

const useHouseholdLedgerMock = vi.hoisted(() => vi.fn())
const useHouseholdFactsMock = vi.hoisted(() => vi.fn())
const categorizeMutateAsync = vi.hoisted(() => vi.fn())
const categorizeIsPending = vi.hoisted(() => ({ value: false }))
const useTransactionPurchaseItemsMock = vi.hoisted(() => vi.fn())
const categorizeItemMutateAsync = vi.hoisted(() => vi.fn())
const setItemOwnerMutateAsync = vi.hoisted(() => vi.fn())

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdLedger: useHouseholdLedgerMock,
  useHouseholdFacts: useHouseholdFactsMock,
  useCategorizeHouseholdTransaction: () => ({
    mutateAsync: categorizeMutateAsync,
    isPending: categorizeIsPending.value,
  }),
}))

vi.mock('@/lib/hooks/useHouseholdPurchases', () => ({
  useTransactionPurchaseItems: useTransactionPurchaseItemsMock,
  useCategorizePurchaseItem: () => ({
    mutateAsync: categorizeItemMutateAsync,
    isPending: false,
  }),
  useSetPurchaseItemOwner: () => ({
    mutateAsync: setItemOwnerMutateAsync,
    isPending: false,
  }),
}))

const PAGE_SIZE = 50

function buildEntry(index: number, overrides = {}) {
  const padded = String(index).padStart(3, '0')
  return {
    id: `txn-${padded}`,
    kind: 'transaction',
    flowType: 'expense',
    direction: 'debit',
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
    itemCount: 0,
    itemCategories: [],
    ...overrides,
  }
}

function buildPurchaseItem(index: number, overrides = {}) {
  return {
    id: `item-${index}`,
    transactionId: 'txn-001',
    productId: `product-${index}`,
    productName: `Product ${index}`,
    productMatchStatus: 'matched',
    productMatchConfidence: 0.98,
    purchaseDate: '2026-04-02',
    merchant: 'Merchant 001',
    description: `Item ${index}`,
    quantity: 1,
    unitPrice: null,
    amount: 2.5,
    allocatedAmount: 2.5,
    category: 'Groceries',
    essentiality: 'essential',
    categorizationSource: 'item_rules',
    ownerName: null,
    ownerSource: 'none',
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
      categoryOptions: ['groceries', 'Healthcare'],
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
    useHouseholdFactsMock.mockReset()
    categorizeMutateAsync.mockReset()
    categorizeIsPending.value = false
    useTransactionPurchaseItemsMock.mockReset()
    useTransactionPurchaseItemsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
    })
    categorizeItemMutateAsync.mockReset()
    setItemOwnerMutateAsync.mockReset()
    useHouseholdFactsMock.mockReturnValue({ data: [] })
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

  it('renders API-sync provenance with acronym casing', () => {
    mockLedgerPage([
      buildEntry(1, { sourceType: 'plaid', documentType: 'api_sync' }),
    ])

    render(<MoneyLedgerPanel />)

    expect(screen.getByText('Plaid · API sync')).toBeInTheDocument()
    expect(screen.queryByText('Plaid · Api sync')).not.toBeInTheDocument()
  })

  it('shows no filter chips while every filter is at its default', () => {
    mockLedgerPage([buildEntry(1)])

    render(<MoneyLedgerPanel />)

    expect(
      screen.queryByRole('button', { name: 'Clear all' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/clear \w+ filter/i)).not.toBeInTheDocument()
  })

  it('shows chips for active filters and resets a single filter from its chip', async () => {
    const user = userEvent.setup()
    mockLedgerPage([buildEntry(1)])

    render(<MoneyLedgerPanel />)

    await user.click(screen.getByRole('button', { name: '3M' }))
    await user.type(screen.getByLabelText('Search ledger rows'), 'walmart')

    expect(screen.getByLabelText('Clear window filter')).toBeInTheDocument()
    expect(screen.getByText('"walmart"')).toBeInTheDocument()
    expect(lastLedgerParams().window).toBe('3m')

    await user.click(screen.getByLabelText('Clear window filter'))

    expect(lastLedgerParams().window).toBe('all')
    expect(
      screen.queryByLabelText('Clear window filter'),
    ).not.toBeInTheDocument()
    // The untouched search chip stays active.
    expect(screen.getByText('"walmart"')).toBeInTheDocument()
  })

  it('restores all filter defaults from Clear all', async () => {
    const user = userEvent.setup()
    mockLedgerPage([buildEntry(1)])

    render(<MoneyLedgerPanel />)

    await user.click(screen.getByRole('button', { name: '1M' }))
    await user.type(screen.getByLabelText('Search ledger rows'), 'target')
    await waitFor(() => {
      expect(lastLedgerParams().search).toBe('target')
    })

    await user.click(screen.getByRole('button', { name: 'Clear all' }))

    await waitFor(() => {
      expect(lastLedgerParams()).toMatchObject({
        window: 'all',
        kind: 'transactions',
        status: 'canonical',
        account: 'all',
        search: '',
      })
    })
    expect(
      screen.queryByRole('button', { name: 'Clear all' }),
    ).not.toBeInTheDocument()
    expect(screen.getByLabelText('Search ledger rows')).toHaveValue('')
  })

  it('recategorizes a transaction row through the canonical categorize mutation', async () => {
    const user = userEvent.setup()
    categorizeMutateAsync.mockResolvedValue(true)
    mockLedgerPage([
      buildEntry(1, { category: 'Retail', essentiality: 'discretionary' }),
    ])

    render(<MoneyLedgerPanel />)

    const categoryInput = screen.getByLabelText('Category for Merchant 001')
    await user.click(categoryInput)
    expect(categoryInput).toHaveValue('Retail')

    await user.click(screen.getByRole('option', { name: /Personal Care/ }))

    expect(categorizeMutateAsync).toHaveBeenCalledWith({
      transactionId: 'txn-001',
      category: 'Personal Care',
      essentiality: 'discretionary',
      applyToMerchant: false,
    })
  })

  it('offers no category editing on import rows', () => {
    mockLedgerPage([
      buildEntry(1, {
        kind: 'import_row',
        datasetType: 'statement_csv',
        flowType: null,
      }),
    ])

    render(<MoneyLedgerPanel />)

    expect(screen.queryByLabelText(/Category for/)).not.toBeInTheDocument()
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

  it('offers no items button when a row has no purchase items', () => {
    mockLedgerPage([buildEntry(1)])

    render(<MoneyLedgerPanel />)

    expect(
      screen.queryByRole('button', { name: /\d+ items?/ }),
    ).not.toBeInTheDocument()
  })

  it('shows the split categories line for multi-category itemized charges', () => {
    mockLedgerPage([
      buildEntry(1, {
        itemCount: 17,
        itemCategories: ['Groceries', 'Household'],
      }),
    ])

    render(<MoneyLedgerPanel />)

    expect(screen.getByText('Split: Groceries · Household')).toBeInTheDocument()
  })

  it('shows purchase items inline behind an itemized charge with the allocation line', () => {
    mockLedgerPage([
      buildEntry(1, { itemCount: 2, itemCategories: ['Groceries'] }),
    ])
    useTransactionPurchaseItemsMock.mockReturnValue({
      data: [
        buildPurchaseItem(1),
        buildPurchaseItem(2, { amount: 8.5, allocatedAmount: 8.5 }),
      ],
      isLoading: false,
    })

    render(<MoneyLedgerPanel />)

    expect(useTransactionPurchaseItemsMock).toHaveBeenCalledWith('txn-001')
    expect(screen.getByText('Item 1')).toBeInTheDocument()
    expect(screen.getByText('Item 2')).toBeInTheDocument()
    // buildEntry(1).amount is 11; 2.50 + 8.50 reconciles exactly.
    expect(screen.getByText(/matches the charge exactly/)).toBeInTheDocument()
  })

  it('recategorizes a purchase item through the item categorize mutation', async () => {
    const user = userEvent.setup()
    categorizeItemMutateAsync.mockResolvedValue(true)
    mockLedgerPage([
      buildEntry(1, { itemCount: 2, itemCategories: ['Groceries'] }),
    ])
    useTransactionPurchaseItemsMock.mockReturnValue({
      data: [
        buildPurchaseItem(1),
        buildPurchaseItem(2, { amount: 8.5, allocatedAmount: 8.5 }),
      ],
      isLoading: false,
    })

    render(<MoneyLedgerPanel />)

    await user.click(screen.getByLabelText('Category for Item 1'))
    await user.click(screen.getByRole('option', { name: 'Household' }))

    expect(categorizeItemMutateAsync).toHaveBeenCalledWith({
      itemId: 'item-1',
      category: 'Household',
      essentiality: 'essential',
      applyToProduct: false,
    })
  })

  it('sets a purchase item owner from the named owner dropdown', async () => {
    const user = userEvent.setup()
    setItemOwnerMutateAsync.mockResolvedValue(true)
    mockLedgerPage([
      buildEntry(1, { itemCount: 2, itemCategories: ['Groceries'] }),
    ])
    useTransactionPurchaseItemsMock.mockReturnValue({
      data: [
        buildPurchaseItem(1),
        buildPurchaseItem(2, { amount: 8.5, allocatedAmount: 8.5 }),
      ],
      isLoading: false,
    })

    render(<MoneyLedgerPanel />)

    const ownerInput = screen.getByLabelText('Owner for Item 1')
    await user.click(ownerInput)
    await user.click(screen.getByRole('option', { name: 'Cats' }))
    expect(ownerInput).toHaveValue('Cats')

    expect(setItemOwnerMutateAsync).toHaveBeenCalledWith({
      itemId: 'item-1',
      ownerName: 'Cats',
      applyToProduct: false,
    })
  })
})
