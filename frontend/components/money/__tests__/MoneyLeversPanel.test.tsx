'use client'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { HouseholdPriceInsight } from '@/lib/api/household'
import { MoneyLeversPanel } from '../MoneyLeversPanel'

const useHouseholdSpendingMock = vi.fn()
const usePriceCheckStatusMock = vi.fn()
const useHouseholdProductsMock = vi.fn()
const triggerPriceCheckMock = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdSpending: (params?: { window?: string }) =>
    useHouseholdSpendingMock(params),
}))

vi.mock('@/lib/hooks/useHouseholdPurchases', () => ({
  useHouseholdProducts: () => useHouseholdProductsMock(),
  usePriceCheckStatus: () => usePriceCheckStatusMock(),
  useTriggerPriceCheck: () => ({
    mutate: triggerPriceCheckMock,
    isPending: false,
  }),
}))

const categories = [
  {
    category: 'Retail',
    essentiality: 'discretionary',
    totalSpend: 3600,
    averageMonthlySpend: 1200,
    shareOfSpend: 0.3,
    transactionCount: 22,
  },
  {
    category: 'Subscriptions',
    essentiality: 'discretionary',
    totalSpend: 900,
    averageMonthlySpend: 300,
    shareOfSpend: 0.08,
    transactionCount: 12,
  },
  {
    category: 'Travel',
    essentiality: 'discretionary',
    totalSpend: 300,
    averageMonthlySpend: 100,
    shareOfSpend: 0.03,
    transactionCount: 4,
  },
  {
    category: 'Groceries',
    essentiality: 'essential',
    totalSpend: 750,
    averageMonthlySpend: 250,
    shareOfSpend: 0.06,
    transactionCount: 10,
  },
]

function makeTransaction(
  merchant: string,
  category: string,
  essentiality: string,
  amount: number,
  id: string,
) {
  return {
    id,
    date: '2026-03-20',
    merchant,
    description: merchant,
    amount,
    category,
    essentiality,
    categoryConfidence: 0.84,
    needsCategoryReview: false,
    accountLabel: 'Checking',
    sourceDocumentId: 'doc-1',
    sourceKind: 'transaction',
    sourceType: 'bank',
    documentType: 'statement',
  }
}

function mockSpending() {
  useHouseholdSpendingMock.mockReturnValue({
    data: {
      generatedAt: '2026-04-24T00:00:00Z',
      summary: {
        timeframeKey: '3m',
        timeframeLabel: '3 months',
        totalSpend: 6000,
        averageMonthlySpend: 2000,
        transactionCount: 5,
        coverageMonths: 3,
        accountCount: 2,
      },
      categories,
      monthlyTrend: [],
      categoryMonthlyTrend: [],
      transactions: [
        makeTransaction('Amazon', 'Retail', 'discretionary', 600, 'txn-amazon'),
        makeTransaction('Target', 'Retail', 'discretionary', 300, 'txn-target'),
        makeTransaction('Chipotle', 'Dining', 'discretionary', 200, 'txn-chip'),
        makeTransaction('Publix', 'Groceries', 'essential', 250, 'txn-publix'),
      ],
    },
    error: null,
    refetch: vi.fn(),
    isFetching: false,
    isLoading: false,
  })
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

describe('MoneyLeversPanel', () => {
  beforeEach(() => {
    useHouseholdSpendingMock.mockReset()
    usePriceCheckStatusMock.mockReset()
    useHouseholdProductsMock.mockReset()
    triggerPriceCheckMock.mockReset()
    usePriceCheckStatusMock.mockReturnValue({
      data: { openFindings: [], latestRun: null },
    })
    useHouseholdProductsMock.mockReturnValue({
      data: { products: [] },
    })
    mockSpending()
  })

  it('routes price-drift signals to outside-the-norm actions', () => {
    render(<MoneyLeversPanel priceInsights={[unitPriceUpInsight]} />)

    expect(screen.getByText('Outside the norm')).toBeInTheDocument()
    expect(
      screen.getByText('Olive Oil price is outside normal'),
    ).toBeInTheDocument()
    expect(screen.getByText('Run price check before rebuy')).toBeInTheDocument()
  })

  it('shows cheaper-elsewhere price-check findings as concrete levers', () => {
    usePriceCheckStatusMock.mockReturnValue({
      data: {
        openFindings: [
          {
            id: 'finding-1',
            kind: 'cheaper_elsewhere',
            status: 'open',
            productName: 'Olive Oil',
            vendorKey: 'walmart',
            savingsEstimate: 4.25,
            householdPrice: 14,
            vendorPrice: 9.75,
            vendorTitle: 'Great Value Olive Oil',
            vendorPackageLabel: '16.9 oz',
          },
        ],
      },
    })

    render(<MoneyLeversPanel priceInsights={[]} />)

    expect(screen.getByText('Verified item savings')).toBeInTheDocument()
    expect(
      screen.getByText('Buy Great Value Olive Oil at Walmart'),
    ).toBeInTheDocument()
    expect(screen.getByText('Save $4.25/rebuy')).toBeInTheDocument()
    expect(screen.getByText('Verified')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Stored vendor quote; this is a concrete per-rebuy saving.',
      ),
    ).toBeInTheDocument()
  })

  it('keeps modeled spend pressure separate from price-drift deviations', () => {
    render(<MoneyLeversPanel priceInsights={[unitPriceUpInsight]} />)

    const deviation = screen.getByText('Olive Oil price is outside normal')
    const categoryLever = screen.getByText('Retail is biggest trim lever')
    expect(
      deviation.compareDocumentPosition(categoryLever) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy()
  })

  it('flags the merchant lever as non-stackable when it sits inside the category lever', () => {
    render(<MoneyLeversPanel priceInsights={[]} />)

    expect(screen.getByText('Amazon is merchant drag')).toBeInTheDocument()
    expect(
      screen.getByText(/Already inside the Retail category lever/i),
    ).toBeInTheDocument()
  })

  it('labels trim cards as modeled rules of thumb', () => {
    render(<MoneyLeversPanel priceInsights={[]} />)

    expect(screen.getAllByText('Modeled').length).toBeGreaterThan(0)
    expect(
      screen.getAllByText(/rule of thumb, not a guaranteed saving/i).length,
    ).toBeGreaterThan(0)
  })

  it('shows the modeled trim rate on each lever footnote', () => {
    render(<MoneyLeversPanel priceInsights={[unitPriceUpInsight]} />)

    // Retail category lever models at 12%, subscriptions at 20%.
    expect(
      screen.getByText(
        'Modeled at 12% trim — rule of thumb, not a guaranteed saving.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'Modeled at 20% trim — rule of thumb, not a guaranteed saving.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('$40/mo')).not.toBeInTheDocument()
  })

  it('narrows category surfaces when searching a merchant name', async () => {
    const user = userEvent.setup()
    render(<MoneyLeversPanel priceInsights={[]} />)

    // Travel has no matching merchant, so a merchant search must hide its row.
    expect(screen.getByText('Travel')).toBeInTheDocument()

    await user.type(screen.getByLabelText('Search savings levers'), 'Amazon')

    expect(
      screen.getByText('Spend categories matching search'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Travel')).not.toBeInTheDocument()
  })

  it('renders whole-dollar headline stats and the modeled trim column with its rate', () => {
    render(<MoneyLeversPanel priceInsights={[]} />)

    // Window spend / Avg monthly switched from cents to whole dollars.
    expect(screen.getByText('$6,000')).toBeInTheDocument()
    expect(screen.getByText('$2,000')).toBeInTheDocument()

    // Category Pressure column shows the dollar trim plus the modeled rate.
    expect(screen.getByText('Modeled trim')).toBeInTheDocument()
    expect(screen.queryByText('Trim rule')).not.toBeInTheDocument()
    // Retail: $1,200/mo * 12% = $144.
    expect(screen.getByText('$144 · 12%')).toBeInTheDocument()
  })

  it('shows a search-specific empty state when no levers match the search', async () => {
    const user = userEvent.setup()
    render(<MoneyLeversPanel priceInsights={[]} />)

    await user.type(screen.getByLabelText('Search savings levers'), 'zzz')

    expect(
      screen.getByText('No savings actions match this search.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'Clear the search or widen the window to see prioritized savings work.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText('Go to Intake')).not.toBeInTheDocument()
  })

  it('points sparse-data households to Intake when there is nothing to rank', () => {
    useHouseholdSpendingMock.mockReturnValue({
      data: {
        generatedAt: '2026-04-24T00:00:00Z',
        summary: {
          timeframeKey: '3m',
          timeframeLabel: '3 months',
          totalSpend: 0,
          averageMonthlySpend: 0,
          transactionCount: 0,
          coverageMonths: 0,
          accountCount: 0,
        },
        categories: [],
        monthlyTrend: [],
        categoryMonthlyTrend: [],
        transactions: [],
      },
      error: null,
      refetch: vi.fn(),
      isFetching: false,
      isLoading: false,
    })
    render(<MoneyLeversPanel priceInsights={[]} />)

    expect(
      screen.getByText('Not enough spend history to prioritize savings.'),
    ).toBeInTheDocument()
    const intakeLink = screen.getByRole('link', { name: 'Go to Intake' })
    expect(intakeLink).toHaveAttribute('href', '/money?tab=intake')
  })
})
