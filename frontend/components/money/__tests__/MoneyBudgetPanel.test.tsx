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
const useHouseholdDashboardMock = vi.fn()
const confirmFactMutateAsync = vi.fn()
const categorizeMutateAsync = vi.fn()
const setTransactionOwnerMutateAsync = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useCategorizeHouseholdTransaction: () => ({
    mutateAsync: categorizeMutateAsync,
    isPending: false,
  }),
  useSetHouseholdTransactionOwner: () => ({
    mutateAsync: setTransactionOwnerMutateAsync,
    isPending: false,
  }),
  useHouseholdSpending: (params?: { month?: string }) =>
    useHouseholdSpendingMock(params),
  useHouseholdFacts: () => useHouseholdFactsMock(),
  useHouseholdDashboard: () => useHouseholdDashboardMock(),
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
        month: '2026-04',
        monthLabel: 'April 2026',
        isMonthToDate: false,
        daysElapsed: 30,
        daysInMonth: 30,
        basisLabel: 'full month',
        totalSpend: 15099,
        averageMonthlySpend: 5033,
        transactionCount: 62,
        coverageMonths,
        coverageMonthKeys: ['2026-01', '2026-02', '2026-03'].slice(
          0,
          coverageMonths,
        ),
        everydaySpend: 15099,
        oneTimeSpend: 0,
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
      availableMonths: ['2026-01', '2026-02', '2026-03', '2026-04'],
      comparators: [
        {
          key: 'prior_month',
          label: 'March 2026',
          basis: 'full_month',
          basisLabel: 'full month',
          monthsUsed: ['2026-03'],
          totalSpend: 4000,
          totalIncome: 8000,
          netCashFlow: 4000,
          spendChange: 11099,
          spendChangePct: 2.77,
        },
      ],
      oneTimePurchases: [],
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
    useHouseholdDashboardMock.mockReset()
    useHouseholdDashboardMock.mockReturnValue({
      data: undefined,
      isLoading: false,
    })
    confirmFactMutateAsync.mockReset()
    categorizeMutateAsync.mockReset()
    setTransactionOwnerMutateAsync.mockReset()
    useHouseholdFactsMock.mockReturnValue({ data: [] })
    mockSpending()
  })

  it('renders the backend summary stats verbatim, never row math', () => {
    render(<MoneyBudgetPanel />)

    expect(screen.getByText('Caps waiting on you')).toBeInTheDocument()
    // Row math would say $2,750 (1400 + 1100 + 250); the summary says $2,880.
    expect(
      screen.getByText('suggested rows not accepted yet · $2,880'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/\$2,750/)).not.toBeInTheDocument()
    // The cap totals, the budgeted-category count and the over-budget count
    // were four more tiles here; the verdict line above states all of them.
    expect(screen.queryByText('Confirmed cap total')).not.toBeInTheDocument()
    expect(screen.queryByText('Budgeted categories')).not.toBeInTheDocument()
    // Row-level breach badges still come from the rows themselves, and they are
    // judged on the month being reported rather than on the run-rate: Groceries
    // spent $738 against a $250 cap, which is over however tame its average is.
    expect(screen.getAllByText('Over suggested cap')).toHaveLength(3)
    expect(screen.queryByText('Suggested cap')).not.toBeInTheDocument()
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

    // Confirming a fact changes the rows, but the summary stat stays
    // backend-owned: still $2,880 / 4 rows, never re-derived to $1,650 / 2.
    expect(
      screen.getByText('suggested rows not accepted yet · $2,880'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/\$1,650/)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Monthly budget for Retail')).toHaveValue(
      '1200',
    )
    expect(screen.getByText('Accepted cap')).toBeInTheDocument()
    expect(screen.getAllByText('Over confirmed cap')).not.toHaveLength(0)
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
      screen.getByText('suggested rows not accepted yet · $0'),
    ).toBeInTheDocument()
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

  it('keeps three tiles that are each a thing to do, and drops the other seven', () => {
    render(<MoneyBudgetPanel />)

    expect(screen.getByText('Unknown purchases')).toBeInTheDocument()
    expect(screen.getByText('Caps waiting on you')).toBeInTheDocument()
    expect(screen.getByText('Connected MTD spend')).toBeInTheDocument()
    // Each of these was a true number that another element on this screen
    // already says: the comparator row for income and the run-rate, Left over
    // for net cash flow and the savings rate, the verdict line for the caps.
    for (const retired of [
      'Monthly run-rate',
      'Monthly income',
      'Net cash flow',
      'Savings rate',
      'Suggested cap total',
      'Confirmed cap total',
      'Budgeted categories',
    ]) {
      expect(screen.queryByText(retired)).not.toBeInTheDocument()
    }
    // The month selector replaced the 1M/3M/6M/12M chips (D3).
    expect(screen.getByLabelText('Month')).toBeInTheDocument()
    expect(screen.queryByText('12M')).not.toBeInTheDocument()
    expect(screen.getByText('vs March 2026')).toBeInTheDocument()
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
    await user.click(
      screen.getByRole('checkbox', { name: /Merchant rule for Category for/ }),
    )
    await user.click(screen.getByLabelText('Category for Walmart'))
    await user.click(screen.getByRole('option', { name: 'Groceries' }))

    expect(categorizeMutateAsync).toHaveBeenLastCalledWith({
      transactionId: 'txn-household',
      category: 'Groceries',
      essentiality: 'mixed',
      applyToMerchant: true,
    })
  })

  it('sets an owner on a budget drill-down purchase', async () => {
    const user = userEvent.setup()
    setTransactionOwnerMutateAsync.mockResolvedValue({ ok: true })

    render(<MoneyBudgetPanel />)

    await user.click(budgetCategoryButton('Household'))
    await user.click(
      screen.getByRole('checkbox', {
        name: 'Merchant owner rule for Owner for Walmart',
      }),
    )
    await user.click(screen.getByLabelText('Owner for Walmart'))
    await user.click(screen.getByRole('option', { name: 'Cats' }))

    expect(setTransactionOwnerMutateAsync).toHaveBeenLastCalledWith({
      transactionId: 'txn-household',
      ownerName: 'Cats',
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
  it('answers "can we actually spend this" on the review screen itself', () => {
    // The figure lived one tab away on the Decision Board, so the screen where
    // the month is judged could not say whether there was money to act on it.
    useHouseholdDashboardMock.mockReturnValue({
      isLoading: false,
      data: {
        overview: { monthlySpendStatus: 'trusted', netWorthStatus: 'trusted' },
        budgetSnapshot: {
          affordability: {
            freeToSpend: 11828.34,
            cashOnHand: 30494.75,
            billsDue: 88.38,
            billsDueThrough: '2026-09-06',
            remainingEssentials: 1290.32,
            essentialsBasis:
              '5,000 of the 5,000 essentials baseline is covered so far in August.',
            committedFunds: 0,
            cardBalances: 17287.71,
            missingInputs: [],
            status: 'estimate',
            headline:
              '$11,828 free to spend once everything owed through Sep 6 is covered.',
            detail: 'Cash on hand, less bills due through Sep 6.',
          },
        },
      },
    })

    render(<MoneyBudgetPanel />)

    // Card heading and the total line of the subtraction under it.
    expect(screen.getAllByText('Free to spend')).toHaveLength(2)
    expect(
      screen.getByText(
        '$11,828 free to spend once everything owed through Sep 6 is covered.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText('$30,495')).toBeInTheDocument()
  })

  it('names which input is behind rather than a generic stale-data line', () => {
    useHouseholdDashboardMock.mockReturnValue({
      isLoading: false,
      data: {
        overview: { monthlySpendStatus: 'estimated', netWorthStatus: 'stale' },
        budgetSnapshot: {
          affordability: {
            freeToSpend: 11828.34,
            cashOnHand: 30494.75,
            billsDue: 88.38,
            billsDueThrough: '2026-09-06',
            remainingEssentials: 1290.32,
            essentialsBasis: 'basis',
            committedFunds: 0,
            cardBalances: 17287.71,
            missingInputs: [],
            status: 'estimate',
            headline: '$11,828 free to spend.',
            detail: 'Cash on hand, less bills due through Sep 6.',
          },
        },
      },
    })

    render(<MoneyBudgetPanel />)

    expect(
      screen.getByText('Cash and card balances need a refresh.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText("This month's essentials are still an estimate."),
    ).toBeInTheDocument()
    expect(screen.getByText('$11,828 free to spend.')).toBeInTheDocument()
  })
  it('puts the retirement plan on the screen where the month is reviewed', () => {
    // D13's two-way link: the plan assumes a monthly retirement spend and the
    // month being reviewed shows what actually goes out. This is the one screen
    // that has both, so it is where the gap gets noticed.
    useHouseholdDashboardMock.mockReturnValue({
      isLoading: false,
      data: {
        overview: { monthlySpendStatus: 'trusted', netWorthStatus: 'trusted' },
        budgetSnapshot: { affordability: null },
        retirementContributionTracker: {
          status: 'short',
          monthlyTarget: null,
          estimatedMonthlyContributions: 0,
          monthlyGap: 0,
          phase: 'drawing_down',
          phaseLabel: 'Go-go years - 26 years to the next',
          headline:
            'Spending runs $10,231/mo against the $6,429/mo today\u2019s assets support at your own withdrawal rule.',
          detail:
            'The plan assumes $7,500/mo; actual spending is $2,731/mo above it.',
          currentAge: 49,
          targetRetirementAge: 49,
          yearsToTarget: 0,
          investableAssets: 1542870.67,
          withdrawalRate: 0.05,
          sustainableMonthlySpend: 6428.63,
          targetMonthlySpend: 7500,
          assetGap: 257129.33,
          spendPhase: 'go_go',
          yearsToNextSpendPhase: 26,
          blindSpots: [],
        },
      },
    })

    render(<MoneyBudgetPanel />)

    expect(screen.getByText('Retirement plan')).toBeInTheDocument()
    expect(
      screen.getByText('Go-go years - 26 years to the next'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/actual spending is \$2,731\/mo above it/),
    ).toBeInTheDocument()
  })
})
