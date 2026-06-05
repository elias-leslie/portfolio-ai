'use client'

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  CATEGORY_BUDGET_PREFIX,
  serializeCategoryBudgetMeta,
} from '../household-fact-metadata'
import { MoneyBudgetPanel } from '../MoneyBudgetPanel'

const useHouseholdSpendingMock = vi.fn()
const useHouseholdFactsMock = vi.fn()
const confirmFactMutateAsync = vi.fn()
const categorizeMutateAsync = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useCategorizeHouseholdTransaction: () => ({
    mutateAsync: categorizeMutateAsync,
    isPending: false,
  }),
  useHouseholdSpending: (params?: { window?: string }) =>
    useHouseholdSpendingMock(params),
  useHouseholdFacts: () => useHouseholdFactsMock(),
  useConfirmFact: () => ({
    mutateAsync: confirmFactMutateAsync,
    isPending: false,
  }),
}))

vi.mock('recharts', () => {
  const MockChart = ({ children }: { children?: ReactNode }) => (
    <div>{children}</div>
  )
  const MockPart = () => null

  return {
    ResponsiveContainer: MockChart,
    LineChart: MockChart,
    Line: MockPart,
    Tooltip: MockPart,
    XAxis: MockPart,
    YAxis: MockPart,
  }
})

// foundMonthlyBudget now comes from the server (the client no longer recomputes
// it); these mirror what the backend rollup would return for coverage >= 2 months.
const categories = [
  {
    category: 'Household',
    essentiality: 'mixed',
    totalSpend: 4446,
    averageMonthlySpend: 1482,
    shareOfSpend: 0.4,
    transactionCount: 30,
    foundMonthlyBudget: 1400,
  },
  {
    category: 'Retail',
    essentiality: 'discretionary',
    totalSpend: 3861,
    averageMonthlySpend: 1287,
    shareOfSpend: 0.35,
    transactionCount: 22,
    foundMonthlyBudget: 1100,
  },
  {
    category: 'Groceries',
    essentiality: 'essential',
    totalSpend: 738,
    averageMonthlySpend: 246,
    shareOfSpend: 0.08,
    transactionCount: 10,
    foundMonthlyBudget: 250,
  },
]

function mockSpending(coverageMonths = 3) {
  useHouseholdSpendingMock.mockReturnValue({
    data: {
      generatedAt: '2026-04-24T00:00:00Z',
      summary: {
        timeframeKey: '3m',
        timeframeLabel: '3 months',
        totalSpend: 15099,
        averageMonthlySpend: 5033,
        transactionCount: 62,
        coverageMonths,
        accountCount: 2,
        averageMonthlyIncome: 8000,
        netCashFlow: 8901,
        savingsRate: 0.37,
        monthToDateSpend: 1200,
      },
      // Thin coverage: the server returns no suggested cap, so neither does the mock.
      categories:
        coverageMonths < 2
          ? categories.map((category) => ({
              ...category,
              foundMonthlyBudget: null,
            }))
          : categories,
      monthlyTrend: [
        { month: '2026-02', totalSpend: 5000, transactionCount: 20 },
        { month: '2026-03', totalSpend: 5200, transactionCount: 21 },
      ],
      categoryMonthlyTrend: [
        {
          month: '2026-02',
          category: 'Household',
          essentiality: 'mixed',
          totalSpend: 1400,
          transactionCount: 10,
        },
        {
          month: '2026-03',
          category: 'Household',
          essentiality: 'mixed',
          totalSpend: 1600,
          transactionCount: 20,
        },
      ],
      transactions: [
        {
          id: 'txn-household',
          date: '2026-03-20',
          merchant: 'Walmart',
          description: 'WM SUPERCENTER',
          amount: 155.75,
          category: 'Household',
          essentiality: 'mixed',
          categoryConfidence: 0.84,
          needsCategoryReview: false,
          accountLabel: 'Checking',
          sourceDocumentId: 'doc-1',
          sourceKind: 'transaction',
          sourceType: 'bank',
          documentType: 'statement',
        },
      ],
    },
    error: null,
    refetch: vi.fn(),
    isFetching: false,
    isLoading: false,
  })
}

describe('MoneyBudgetPanel', () => {
  beforeEach(() => {
    useHouseholdSpendingMock.mockReset()
    useHouseholdFactsMock.mockReset()
    confirmFactMutateAsync.mockReset()
    categorizeMutateAsync.mockReset()
    useHouseholdFactsMock.mockReturnValue({ data: [] })
    mockSpending()
  })

  it('reconciles top stats when rows only have found budgets', () => {
    render(<MoneyBudgetPanel />)

    expect(screen.getByText('Suggested cap total')).toBeInTheDocument()
    expect(screen.getByText('$2,750')).toBeInTheDocument()
    expect(
      screen.getByText('3 suggested rows not accepted yet.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Confirmed cap total')).toBeInTheDocument()
    expect(
      screen.getByText('Manual or accepted category caps.'),
    ).toBeInTheDocument()
    expect(screen.getByText('3 suggested · 0 confirmed.')).toBeInTheDocument()
    expect(screen.getByText('2 suggested · 0 confirmed.')).toBeInTheDocument()
    expect(screen.getAllByText('Over suggested cap')).toHaveLength(2)
    expect(screen.getByText('Suggested cap')).toBeInTheDocument()
    expect(screen.getByText('Category trendlines')).toBeInTheDocument()
  })

  it('keeps confirmed category budgets separate from found budgets', () => {
    useHouseholdFactsMock.mockReturnValue({
      data: [
        {
          factKey: `${CATEGORY_BUDGET_PREFIX}Retail`,
          factValue: serializeCategoryBudgetMeta({
            category: 'Retail',
            monthlyTarget: 1200,
            source: 'accepted',
            note: 'Accepted cap',
            disabled: false,
          }),
          confirmedAt: '2026-04-24T00:00:00Z',
        },
      ],
    })

    render(<MoneyBudgetPanel />)

    expect(screen.getByText('$1,650')).toBeInTheDocument()
    expect(
      screen.getByText('2 suggested rows not accepted yet.'),
    ).toBeInTheDocument()
    expect(screen.getAllByText('$1,200')).not.toHaveLength(0)
    expect(screen.getByText('2 suggested · 1 confirmed.')).toBeInTheDocument()
    expect(screen.getByText('1 suggested · 1 confirmed.')).toBeInTheDocument()
    expect(screen.getByText('Accepted cap')).toBeInTheDocument()
    expect(screen.getAllByText('Over budget')).not.toHaveLength(0)
  })

  it('shows no-budget state when coverage is too thin to infer found values', () => {
    mockSpending(1)

    render(<MoneyBudgetPanel />)

    expect(
      screen.getByText('0 suggested rows not accepted yet.'),
    ).toBeInTheDocument()
    expect(screen.getAllByText(/0 suggested · 0 confirmed/i)).toHaveLength(2)
    expect(screen.getAllByText('No cap yet')).toHaveLength(3)
  })

  it('surfaces cash-flow KPIs and an accept-all suggested caps action', () => {
    render(<MoneyBudgetPanel />)

    expect(screen.getByText('Savings rate')).toBeInTheDocument()
    expect(screen.getByText('37%')).toBeInTheDocument()
    expect(screen.getByText('Net cash flow')).toBeInTheDocument()
    expect(screen.getByText('Month-to-date spend')).toBeInTheDocument()
    // Default fixture has discretionary categories with suggested (unconfirmed) caps.
    expect(
      screen.getByRole('button', { name: /Accept all .* suggested cap/i }),
    ).toBeInTheDocument()
  })

  it('expands category purchases and sends merchant rule recategorization', async () => {
    const user = userEvent.setup()
    categorizeMutateAsync.mockResolvedValue({ ok: true })

    render(<MoneyBudgetPanel />)

    // The category trend legend now also renders a "Household" toggle button, so
    // target the expandable table row specifically via its aria-expanded handle.
    const householdButtons = screen.getAllByRole('button', {
      name: /household/i,
    })
    const expandRow = householdButtons.find(
      (button) => button.getAttribute('aria-expanded') != null,
    )
    await user.click(expandRow ?? householdButtons[0])
    expect(screen.getByText(/WM SUPERCENTER/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Categorize' }))
    expect(screen.getByRole('option', { name: 'Retail' })).toBeInTheDocument()
    expect(
      screen.getByRole('option', { name: 'Groceries' }),
    ).toBeInTheDocument()

    await user.clear(screen.getByLabelText('Category'))
    await user.type(screen.getByLabelText('Category'), 'Groceries')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(categorizeMutateAsync).toHaveBeenCalledWith({
      transactionId: 'txn-household',
      category: 'Groceries',
      essentiality: 'mixed',
      applyToMerchant: false,
    })
  })
})
