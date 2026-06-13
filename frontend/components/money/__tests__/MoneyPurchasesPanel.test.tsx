'use client'

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { HouseholdPriceInsight } from '@/lib/api/household'
import { MoneyPurchasesPanel } from '../MoneyPurchasesPanel'

const useHouseholdProductsMock = vi.hoisted(() => vi.fn())
const usePurchaseItemReviewQueueMock = vi.hoisted(() => vi.fn())
const useHouseholdProductDetailMock = vi.hoisted(() => vi.fn())
const usePriceCheckStatusMock = vi.hoisted(() => vi.fn())
const useShoppingListsMock = vi.hoisted(() => vi.fn())
const useVendorProfilesMock = vi.hoisted(() => vi.fn())
const assignMutateAsync = vi.hoisted(() => vi.fn())
const mergeMutateAsync = vi.hoisted(() => vi.fn())
const triggerPriceCheckMutate = vi.hoisted(() => vi.fn())
const createShoppingListMutate = vi.hoisted(() => vi.fn())
const importShoppingListMutateAsync = vi.hoisted(() => vi.fn())
const optimizeShoppingListMutate = vi.hoisted(() => vi.fn())
const updateVendorProfilesMutate = vi.hoisted(() => vi.fn())

vi.mock('@/lib/hooks/useHouseholdPurchases', () => ({
  useHouseholdProducts: useHouseholdProductsMock,
  usePurchaseItemReviewQueue: usePurchaseItemReviewQueueMock,
  useHouseholdProductDetail: useHouseholdProductDetailMock,
  usePriceCheckStatus: usePriceCheckStatusMock,
  useShoppingLists: useShoppingListsMock,
  useVendorProfiles: useVendorProfilesMock,
  useAssignPurchaseItemProduct: () => ({
    mutateAsync: assignMutateAsync,
    isPending: false,
  }),
  useMergeHouseholdProducts: () => ({
    mutateAsync: mergeMutateAsync,
    isPending: false,
  }),
  useTriggerPriceCheck: () => ({
    mutate: triggerPriceCheckMutate,
    isPending: false,
  }),
  useCreateShoppingList: () => ({
    mutate: createShoppingListMutate,
    isPending: false,
  }),
  useImportShoppingListItems: () => ({
    mutateAsync: importShoppingListMutateAsync,
    isPending: false,
  }),
  useOptimizeShoppingList: () => ({
    mutate: optimizeShoppingListMutate,
    isPending: false,
  }),
  useUpdateVendorProfiles: () => ({
    mutate: updateVendorProfilesMutate,
    isPending: false,
  }),
}))

function buildProduct(index: number, overrides = {}) {
  const padded = String(index).padStart(3, '0')
  return {
    id: `product-${padded}`,
    canonicalName: `Product ${padded}`,
    brand: 'Great Value',
    packageDisplayLabel: '12 oz',
    imageUrl: null,
    purchaseCount: 3,
    observationCount: 2,
    needsReviewCount: 0,
    firstObservedDate: '2026-01-05',
    lastObservedDate: '2026-04-02',
    latestPrice: 4.5,
    latestUnitPrice: 0.38,
    latestMerchant: 'Walmart',
    pricePoints: [
      {
        observedDate: '2026-01-05',
        merchant: 'Walmart',
        totalPrice: 3.98,
        quantity: 1,
        unitPrice: 0.33,
        source: 'receipt',
      },
      {
        observedDate: '2026-04-02',
        merchant: 'Walmart',
        totalPrice: 4.5,
        quantity: 1,
        unitPrice: 0.38,
        source: 'receipt',
      },
    ],
    ...overrides,
  }
}

function mockCatalog(
  products: ReturnType<typeof buildProduct>[],
  overrides: Record<string, unknown> = {},
) {
  useHouseholdProductsMock.mockReturnValue({
    data: {
      generatedAt: '2026-06-01T00:00:00Z',
      totalCount: products.length,
      needsReviewTotal: 0,
      offset: 0,
      limit: 50,
      returnedCount: products.length,
      products,
      ...overrides,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    isFetching: false,
  })
}

function buildReviewItem(overrides = {}) {
  return {
    id: 'item-review-1',
    transactionId: null,
    productId: 'product-001',
    productName: 'Product 001',
    productMatchStatus: 'needs_review',
    productMatchConfidence: 0.7,
    purchaseDate: '2026-04-02',
    merchant: 'Walmart',
    description: 'GV OLIVE OIL 17OZ',
    quantity: 1,
    unitPrice: null,
    amount: 8.98,
    allocatedAmount: null,
    category: 'Groceries',
    essentiality: 'essential',
    categorizationSource: 'item_rules',
    ...overrides,
  }
}

const unitPriceUpInsight: HouseholdPriceInsight = {
  merchant: 'Walmart',
  itemName: 'Olive Oil',
  signalType: 'unit_price_up',
  latestPrice: 14.0,
  previousPrice: 11.5,
  priceChange: 2.5,
  priceChangePct: 21,
  latestDate: '2026-03-15',
  previousDate: '2026-01-10',
  unitPriceChangePct: 18,
  shrinkflationFlag: false,
  confidence: 0.8,
  recommendation: 'Compare equivalent pack sizes before reordering.',
}

// The review card and detail sheet also call useHouseholdProducts (with
// undefined while their pickers are idle); the catalog's own calls always
// carry a sort, so filter to those.
function lastCatalogParams() {
  return (
    useHouseholdProductsMock.mock.calls
      .map((call) => call[0])
      .filter((params) => params && 'sort' in params)
      .at(-1) ?? {}
  )
}

describe('MoneyPurchasesPanel', () => {
  beforeEach(() => {
    useHouseholdProductsMock.mockReset()
    usePurchaseItemReviewQueueMock.mockReset()
    useHouseholdProductDetailMock.mockReset()
    usePriceCheckStatusMock.mockReset()
    useShoppingListsMock.mockReset()
    useVendorProfilesMock.mockReset()
    assignMutateAsync.mockReset()
    mergeMutateAsync.mockReset()
    triggerPriceCheckMutate.mockReset()
    createShoppingListMutate.mockReset()
    importShoppingListMutateAsync.mockReset()
    optimizeShoppingListMutate.mockReset()
    updateVendorProfilesMutate.mockReset()
    usePurchaseItemReviewQueueMock.mockReturnValue({
      data: { generatedAt: '2026-06-01T00:00:00Z', totalCount: 0, items: [] },
    })
    usePriceCheckStatusMock.mockReturnValue({ data: undefined })
    useShoppingListsMock.mockReturnValue({
      data: { generatedAt: '2026-06-01T00:00:00Z', lists: [] },
      isLoading: false,
    })
    useVendorProfilesMock.mockReturnValue({
      data: { generatedAt: '2026-06-01T00:00:00Z', vendors: [] },
    })
    useHouseholdProductDetailMock.mockReturnValue({
      data: undefined,
      isLoading: false,
    })
  })

  it('renders catalog rows with name, price, and a hoverable sparkline', () => {
    mockCatalog([buildProduct(1), buildProduct(2)])

    render(<MoneyPurchasesPanel priceInsights={[]} />)

    expect(screen.getByText('Product 001')).toBeInTheDocument()
    expect(screen.getAllByText('Great Value · 12 oz')).toHaveLength(2)
    expect(screen.getAllByText('$4.50')).toHaveLength(2)
    expect(screen.getByText('Showing 1-2 of 2 products')).toBeInTheDocument()

    const sparklines = screen.getAllByRole('img', { name: /Price history/ })
    expect(sparklines).toHaveLength(2)

    // Hovering surfaces the nearest observation's full detail.
    fireEvent.mouseMove(sparklines[0], { clientX: 0 })
    const tooltip = screen.getByTestId('price-point-tooltip')
    expect(tooltip).toHaveTextContent('Walmart')
    expect(tooltip).toHaveTextContent('$3.98')
  })

  it('sends the search term to the products query', async () => {
    const user = userEvent.setup()
    mockCatalog([buildProduct(1)])

    render(<MoneyPurchasesPanel priceInsights={[]} />)

    await user.type(screen.getByLabelText('Search products'), 'olive')

    await waitFor(() => {
      expect(lastCatalogParams().search).toBe('olive')
    })
  })

  it('requests the next page by offset and switches sort', async () => {
    const user = userEvent.setup()
    mockCatalog(
      Array.from({ length: 50 }, (_, i) => buildProduct(i + 1)),
      { totalCount: 120, returnedCount: 50 },
    )

    render(<MoneyPurchasesPanel priceInsights={[]} />)

    expect(lastCatalogParams().offset).toBe(0)

    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(lastCatalogParams().offset).toBe(50)

    await user.click(screen.getByRole('button', { name: 'A-Z' }))
    await waitFor(() => {
      expect(lastCatalogParams()).toMatchObject({ sort: 'name', offset: 0 })
    })
  })

  it('shows the review empty state when nothing needs review', () => {
    mockCatalog([])

    render(<MoneyPurchasesPanel priceInsights={[]} />)

    expect(
      screen.getByText(/No product matches waiting on review/),
    ).toBeInTheDocument()
  })

  it('confirms, reassigns, and detaches review-queue items', async () => {
    const user = userEvent.setup()
    assignMutateAsync.mockResolvedValue(true)
    mockCatalog([buildProduct(2)])
    usePurchaseItemReviewQueueMock.mockReturnValue({
      data: {
        generatedAt: '2026-06-01T00:00:00Z',
        totalCount: 1,
        items: [buildReviewItem()],
      },
    })

    render(<MoneyPurchasesPanel priceInsights={[]} />)

    expect(screen.getByText('GV OLIVE OIL 17OZ')).toBeInTheDocument()
    expect(screen.getByText('70% match')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(assignMutateAsync).toHaveBeenCalledWith({
      itemId: 'item-review-1',
      action: 'confirm',
      productId: undefined,
    })

    await user.click(screen.getByRole('button', { name: 'Reassign' }))
    await user.type(
      screen.getByLabelText('Search product for GV OLIVE OIL 17OZ'),
      'product',
    )
    await user.click(
      await screen.findByRole('button', { name: 'Use this product' }),
    )
    expect(assignMutateAsync).toHaveBeenCalledWith({
      itemId: 'item-review-1',
      action: 'reassign',
      productId: 'product-002',
    })

    await user.click(screen.getByRole('button', { name: 'Detach' }))
    expect(assignMutateAsync).toHaveBeenCalledWith({
      itemId: 'item-review-1',
      action: 'detach',
      productId: undefined,
    })
  })

  it('opens the product detail sheet from the Details button', async () => {
    const user = userEvent.setup()
    const product = buildProduct(1)
    mockCatalog([product])
    useHouseholdProductDetailMock.mockReturnValue({
      data: {
        generatedAt: '2026-06-01T00:00:00Z',
        product,
        identifiers: [{ kind: 'upc', value: '012345678905' }],
        observations: product.pricePoints,
        recentItems: [],
      },
      isLoading: false,
    })

    render(<MoneyPurchasesPanel priceInsights={[]} />)

    await user.click(screen.getByRole('button', { name: 'Details' }))

    expect(useHouseholdProductDetailMock).toHaveBeenLastCalledWith(
      'product-001',
    )
    expect(
      screen.getByRole('heading', { name: 'Product 001' }),
    ).toBeInTheDocument()
    expect(screen.getByText('upc')).toBeInTheDocument()
    expect(screen.getByText('Price history')).toBeInTheDocument()
    expect(screen.getByText('Merge duplicate')).toBeInTheDocument()
  })

  it('renders the relocated Price Signals table with signal badges', () => {
    mockCatalog([])

    render(<MoneyPurchasesPanel priceInsights={[unitPriceUpInsight]} />)

    expect(screen.getByText('Price Signals')).toBeInTheDocument()
    expect(screen.getByText('Unit price up')).toBeInTheDocument()
    expect(screen.getByText('Olive Oil')).toBeInTheDocument()
  })

  it('shows the price-signals empty state without evidence', () => {
    mockCatalog([])

    render(<MoneyPurchasesPanel priceInsights={[]} />)

    expect(screen.getByText('No price-drift evidence yet.')).toBeInTheDocument()
  })

  it('shows the price-check empty state and triggers a run', async () => {
    const user = userEvent.setup()
    mockCatalog([])

    render(<MoneyPurchasesPanel priceInsights={[]} />)

    expect(screen.getByText('No price check has run yet.')).toBeInTheDocument()
    expect(screen.getByText('No savings findings yet.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Run price check' }))
    expect(triggerPriceCheckMutate).toHaveBeenCalledTimes(1)
  })

  it('disables the run button and shows progress while a check is active', () => {
    mockCatalog([])
    usePriceCheckStatusMock.mockReturnValue({
      data: {
        generatedAt: '2026-06-12T00:00:00Z',
        latestRun: {
          id: 'run-1',
          status: 'running',
          triggeredBy: 'manual',
          productCount: 0,
          quoteCount: 0,
          findingCount: 0,
          startedAt: '2026-06-12T00:00:00Z',
          finishedAt: null,
          error: null,
          vendors: [],
        },
        openFindings: [],
      },
    })

    render(<MoneyPurchasesPanel priceInsights={[]} />)

    expect(
      screen.getByText('Jenny is checking vendor prices…'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Running…' })).toBeDisabled()
  })

  it('renders a completed run with vendor outcomes and findings', () => {
    mockCatalog([])
    usePriceCheckStatusMock.mockReturnValue({
      data: {
        generatedAt: '2026-06-12T00:00:00Z',
        latestRun: {
          id: 'run-2',
          status: 'completed',
          triggeredBy: 'manual',
          productCount: 12,
          quoteCount: 18,
          findingCount: 2,
          startedAt: '2026-06-12T00:00:00Z',
          finishedAt: '2026-06-12T00:06:00Z',
          error: null,
          vendors: [
            { vendorKey: 'amazon', status: 'ok', quoteCount: 10, error: null },
            {
              vendorKey: 'walmart',
              status: 'blocked',
              quoteCount: 0,
              error: 'robot wall',
            },
          ],
        },
        openFindings: [
          {
            id: 'finding-1',
            kind: 'cheaper_elsewhere',
            status: 'open',
            productId: 'product-001',
            productName: 'Product 001',
            vendorKey: 'walmart',
            savingsEstimate: 5.5,
            householdPrice: 12.49,
            vendorPrice: 6.99,
            vendorUrl: 'https://walmart.com/ip/x',
            detail: null,
            createdAt: '2026-06-12T00:06:00Z',
          },
          {
            id: 'finding-2',
            kind: 'savings_rollup',
            status: 'open',
            savingsEstimate: 31.0,
            detail: '3 products are cheaper elsewhere',
          },
        ],
      },
    })

    render(<MoneyPurchasesPanel priceInsights={[]} />)

    expect(
      screen.getByText(/12 products · 18 quotes · 2 findings/),
    ).toBeInTheDocument()
    expect(screen.getByText('10 quotes')).toBeInTheDocument()
    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0)

    expect(screen.getByText('Product 001')).toBeInTheDocument()
    expect(
      screen.getByText(
        /Walmart quoted a comparable item for \$6\.99 vs your \$12\.49/,
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'view item' })).toHaveAttribute(
      'href',
      'https://walmart.com/ip/x',
    )
    expect(screen.getByText('Save $5.50')).toBeInTheDocument()
    expect(
      screen.getByText('3 products are cheaper elsewhere'),
    ).toBeInTheDocument()
    expect(screen.getByText('Save $31.00')).toBeInTheDocument()
  })

  it('renders shopping-list optimization and triggers optimize', async () => {
    const user = userEvent.setup()
    mockCatalog([])
    useShoppingListsMock.mockReturnValue({
      data: {
        generatedAt: '2026-06-01T00:00:00Z',
        lists: [
          {
            id: 'list-1',
            name: 'Groceries',
            status: 'active',
            items: [
              {
                id: 'item-1',
                productId: 'product-001',
                productName: 'GV Edamame',
                freeText: null,
                quantity: 2,
                unit: 'bags',
                status: 'open',
                position: 0,
                matchConfidence: 0.85,
              },
            ],
            latestOptimization: {
              itemCount: 1,
              matchedItemCount: 1,
              vendorBaskets: [
                {
                  vendorKey: 'walmart',
                  displayName: 'Walmart',
                  itemCount: 1,
                  uncoveredCount: 0,
                  total: 4,
                },
              ],
              bestSingleVendor: {
                vendorKey: 'walmart',
                displayName: 'Walmart',
                itemCount: 1,
                total: 4,
              },
              splitRecommendation: {
                recommended: false,
                savings: 0,
                threshold: 8,
                total: 4,
                assignments: [],
              },
            },
          },
        ],
      },
      isLoading: false,
    })
    useVendorProfilesMock.mockReturnValue({
      data: {
        generatedAt: '2026-06-01T00:00:00Z',
        vendors: [
          {
            vendorKey: 'walmart',
            displayName: 'Walmart',
            enabled: true,
            deliveryFee: 0,
            pickupFee: null,
            freeDeliveryThreshold: null,
            membershipMonthlyFee: null,
            membershipActive: false,
          },
        ],
      },
    })

    render(<MoneyPurchasesPanel priceInsights={[]} />)

    expect(screen.getByText('Groceries')).toBeInTheDocument()
    expect(screen.getByText('1 open item')).toBeInTheDocument()
    expect(screen.getByText(/Best single vendor/)).toBeInTheDocument()
    expect(screen.getAllByText('Walmart').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    expect(optimizeShoppingListMutate).toHaveBeenCalledWith('list-1')
  })
})
