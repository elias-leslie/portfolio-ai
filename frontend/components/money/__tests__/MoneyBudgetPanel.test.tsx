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
    PieChart: MockChart,
    Pie: MockChart,
    Cell: MockPart,
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

function mockSpending(
  coverageMonths = 3,
  transactions: Array<Record<string, unknown>> | null = null,
) {
  const hasBudgetRollup = coverageMonths >= 2
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
        // PARITY PIN: deliberately different from what row math would produce
        // (rows would say found $2,750 across 3 rows with 2 over cap). The
        // stats must render these server numbers verbatim — if a client-side
        // fallback recomputation ever comes back, the assertions below fail.
        foundBudgetTotal: hasBudgetRollup ? 2880 : 0,
        confirmedBudgetTotal: hasBudgetRollup ? 410 : 0,
        budgetedCategoryCount: hasBudgetRollup ? 6 : 0,
        foundBudgetCategoryCount: hasBudgetRollup ? 4 : 0,
        confirmedBudgetCategoryCount: hasBudgetRollup ? 2 : 0,
        overBudgetCount: hasBudgetRollup ? 4 : 0,
        foundOverBudgetCount: hasBudgetRollup ? 3 : 0,
        confirmedOverBudgetCount: hasBudgetRollup ? 1 : 0,
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
      transactions: transactions ?? [
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
          itemCount: 17,
          itemCategories: ['Groceries', 'Household'],
        },
      ],
    },
    error: null,
    refetch: vi.fn(),
    isFetching: false,
    isLoading: false,
  })
}

function budgetCategoryButton(category: string): HTMLButtonElement {
  const button = screen
    .getAllByRole('button', { name: new RegExp(category, 'i') })
    .find((element) => element.getAttribute('aria-expanded') != null)
  if (!button) {
    throw new Error(`Missing expandable budget row for ${category}`)
  }
  return button as HTMLButtonElement
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

  it('renders the backend summary stats verbatim, never row math', () => {
    render(<MoneyBudgetPanel />)

    expect(screen.getByText('Suggested cap total')).toBeInTheDocument()
    // Row math would say $2,750 (1400 + 1100 + 250); the summary says $2,880.
    expect(screen.getByText('$2,880')).toBeInTheDocument()
    expect(screen.queryByText('$2,750')).not.toBeInTheDocument()
    expect(
      screen.getByText('4 suggested rows not accepted yet.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Confirmed cap total')).toBeInTheDocument()
    expect(screen.getByText('$410')).toBeInTheDocument()
    expect(
      screen.getByText('Manual or accepted category caps.'),
    ).toBeInTheDocument()
    expect(screen.getByText('4 suggested · 2 confirmed.')).toBeInTheDocument()
    expect(screen.getByText('3 suggested · 1 confirmed.')).toBeInTheDocument()
    // Row-level breach badges still come from the rows themselves.
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

    // Confirming a fact changes the rows, but the summary stats stay
    // backend-owned: still $2,880 / 4 rows, never re-derived to $1,650 / 2.
    expect(screen.getByText('$2,880')).toBeInTheDocument()
    expect(screen.queryByText('$1,650')).not.toBeInTheDocument()
    expect(
      screen.getByText('4 suggested rows not accepted yet.'),
    ).toBeInTheDocument()
    expect(screen.getAllByText('$1,200')).not.toHaveLength(0)
    expect(screen.getByText('Accepted cap')).toBeInTheDocument()
    expect(screen.getAllByText('Over budget')).not.toHaveLength(0)
  })

  it('saves a default owner inline on the category budget fact', async () => {
    const user = userEvent.setup()
    confirmFactMutateAsync.mockResolvedValue({ ok: true })

    render(<MoneyBudgetPanel />)

    const ownerInput = screen.getByLabelText('Default owner for Household')
    await user.click(ownerInput)
    expect(screen.getByRole('option', { name: 'Mariana' })).toBeInTheDocument()
    expect(
      screen.getByRole('option', { name: 'Mariana/Elias' }),
    ).toBeInTheDocument()
    await user.type(ownerInput, 'Alex Demo')
    await user.keyboard('{Enter}')

    expect(confirmFactMutateAsync).toHaveBeenLastCalledWith({
      factKey: `${CATEGORY_BUDGET_PREFIX}Household`,
      factValue: serializeCategoryBudgetMeta({
        category: 'Household',
        monthlyTarget: null,
        source: 'manual',
        note: '',
        disabled: false,
        ownerName: 'Alex Demo',
      }),
    })
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

  it('renders owner spend from category ownership defaults', () => {
    useHouseholdFactsMock.mockReturnValue({
      data: [
        {
          factKey: `${CATEGORY_BUDGET_PREFIX}Household`,
          factValue: serializeCategoryBudgetMeta({
            category: 'Household',
            monthlyTarget: 1400,
            source: 'manual',
            note: '',
            disabled: false,
            ownerName: 'Alex Demo',
          }),
          confirmedAt: '2026-04-24T00:00:00Z',
        },
      ],
    })

    render(<MoneyBudgetPanel />)

    expect(screen.getByText('Owner spend')).toBeInTheDocument()
    expect(screen.getAllByText('Alex Demo')).not.toHaveLength(0)
    expect(screen.getByText(/1 transaction/)).toBeInTheDocument()
  })

  it('surfaces cash-flow KPIs and an accept-all suggested caps action', () => {
    render(<MoneyBudgetPanel />)

    expect(screen.getByText('Savings rate')).toBeInTheDocument()
    expect(screen.getByText('37%')).toBeInTheDocument()
    expect(screen.getByText('Net cash flow')).toBeInTheDocument()
    // The subtitle names the selected window (default 3M) so the number
    // cannot be misread as a monthly figure.
    expect(
      screen.getByText('Income minus tracked spend over this 3M window.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Month-to-date spend')).toBeInTheDocument()
    // Default fixture has discretionary categories with suggested (unconfirmed) caps.
    expect(
      screen.getByRole('button', { name: /Accept all .* suggested cap/i }),
    ).toBeInTheDocument()
  })

  it('links from the budget table actions to the hidden-categories card', () => {
    useHouseholdFactsMock.mockReturnValue({
      data: [
        {
          factKey: `${CATEGORY_BUDGET_PREFIX}Retail`,
          factValue: serializeCategoryBudgetMeta({
            category: 'Retail',
            monthlyTarget: null,
            source: 'manual',
            note: 'Paused while traveling',
            disabled: true,
          }),
          confirmedAt: '2026-04-24T00:00:00Z',
        },
      ],
    })

    render(<MoneyBudgetPanel />)

    const anchor = screen.getByRole('link', { name: '1 hidden' })
    expect(anchor).toHaveAttribute('href', '#hidden-categories')
    expect(document.getElementById('hidden-categories')).not.toBeNull()
    expect(screen.getByText('Hidden categories')).toBeInTheDocument()
  })

  it('keeps the hidden-categories anchor out of the actions when nothing is hidden', () => {
    render(<MoneyBudgetPanel />)

    expect(screen.queryByRole('link', { name: /hidden/i })).toBeNull()
  })

  it('expands category purchases and recategorizes inline', async () => {
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

    await user.click(screen.getByLabelText('Category for Walmart'))
    expect(screen.getByRole('option', { name: 'Retail' })).toBeInTheDocument()
    expect(
      screen.getByRole('option', { name: 'Groceries' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('option', { name: 'Groceries' }))

    expect(categorizeMutateAsync).toHaveBeenCalledWith({
      transactionId: 'txn-household',
      category: 'Groceries',
      essentiality: 'mixed',
      applyToMerchant: false,
    })
  })

  it('can recategorize a budget transaction as a merchant rule', async () => {
    const user = userEvent.setup()
    categorizeMutateAsync.mockResolvedValue({ ok: true })

    render(<MoneyBudgetPanel />)

    await user.click(budgetCategoryButton('Household'))
    await user.click(screen.getByRole('checkbox', { name: 'Merchant rule' }))
    await user.click(screen.getByLabelText('Category for Walmart'))
    await user.click(screen.getByRole('option', { name: 'Groceries' }))

    expect(categorizeMutateAsync).toHaveBeenLastCalledWith({
      transactionId: 'txn-household',
      category: 'Groceries',
      essentiality: 'mixed',
      applyToMerchant: true,
    })
  })

  it('shows the Split badge on itemized transactions in the drill-down', async () => {
    const user = userEvent.setup()

    render(<MoneyBudgetPanel />)

    const householdButtons = screen.getAllByRole('button', {
      name: /household/i,
    })
    const expandRow = householdButtons.find(
      (button) => button.getAttribute('aria-expanded') != null,
    )
    await user.click(expandRow ?? householdButtons[0])

    const badge = screen.getByText('Split · 17 items')
    expect(badge).toBeInTheDocument()
    expect(badge.closest('[title]')).toHaveAttribute(
      'title',
      'Split across Groceries · Household',
    )
  })

  it('drills category budgets into itemized purchase portions', async () => {
    const user = userEvent.setup()
    mockSpending(3, [
      {
        id: 'txn-amazon',
        date: '2026-03-20',
        merchant: 'Amazon',
        description: 'Amazon mixed order',
        amount: 100,
        category: 'Retail',
        essentiality: 'discretionary',
        categoryConfidence: 0.84,
        needsCategoryReview: false,
        accountLabel: 'Checking',
        sourceDocumentId: 'doc-1',
        sourceKind: 'transaction',
        sourceType: 'bank',
        documentType: 'statement',
        itemCount: 2,
        itemCategories: ['Groceries', 'Retail'],
        itemSplits: [
          {
            category: 'Groceries',
            essentiality: 'essential',
            amount: 45,
            itemCount: 1,
            ownerName: 'Alex Demo',
          },
          {
            category: 'Retail',
            essentiality: 'discretionary',
            amount: 55,
            itemCount: 1,
          },
        ],
      },
    ])

    render(<MoneyBudgetPanel />)

    await user.click(budgetCategoryButton('Groceries'))

    expect(screen.getByText(/Amazon mixed order/)).toBeInTheDocument()
    expect(screen.getAllByText('$45.00')).not.toHaveLength(0)
    expect(screen.getByText('Itemized portion')).toBeInTheDocument()
    expect(screen.getByText(/Owner: Alex Demo/)).toBeInTheDocument()
  })
})
