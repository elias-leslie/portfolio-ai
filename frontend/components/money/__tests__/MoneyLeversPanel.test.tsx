'use client'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { HouseholdPriceInsight } from '@/lib/api/household'
import { MoneyLeversPanel } from '../MoneyLeversPanel'

const useHouseholdSpendingMock = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdSpending: (params?: { window?: string }) =>
    useHouseholdSpendingMock(params),
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
    mockSpending()
  })

  it('fires the price-signal lever for unit_price_up data', () => {
    render(<MoneyLeversPanel priceInsights={[unitPriceUpInsight]} />)

    // The lever (not just the table row) only appears when the signal passes the
    // bestPriceSignal filter — the regression was that unit_price_up was excluded.
    expect(
      screen.getByText('Olive Oil price drift needs a check'),
    ).toBeInTheDocument()
  })

  it('renders a Unit Price Up badge in the Price Signals table', () => {
    render(<MoneyLeversPanel priceInsights={[unitPriceUpInsight]} />)

    expect(screen.getByText('Unit price up')).toBeInTheDocument()
  })

  it('ranks the highest-savings category lever above the price-signal lever', () => {
    render(<MoneyLeversPanel priceInsights={[unitPriceUpInsight]} />)

    const categoryLever = screen.getByText('Retail is biggest trim lever')
    const priceLever = screen.getByText('Olive Oil price drift needs a check')
    expect(
      categoryLever.compareDocumentPosition(priceLever) &
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
    // Price-signal savings are a share of total monthly spend, not a trim.
    expect(
      screen.getByText(
        'Modeled at 2% of monthly spend — rule of thumb, not a guaranteed saving.',
      ),
    ).toBeInTheDocument()
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

    expect(screen.getByText('No levers match this search.')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Clear the search or widen the window to see ranked trim levers.',
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
      screen.getByText(
        'Not enough spend history in this window to rank trims.',
      ),
    ).toBeInTheDocument()
    const intakeLink = screen.getByRole('link', { name: 'Go to Intake' })
    expect(intakeLink).toHaveAttribute('href', '/money?tab=intake')
  })
})
