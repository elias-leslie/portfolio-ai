'use client'

import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  CATEGORY_BUDGET_PREFIX,
  serializeCategoryBudgetMeta,
} from '../household-fact-metadata'
import { MoneyBudgetPanel } from '../MoneyBudgetPanel'

const useHouseholdSpendingMock = vi.fn()
const useHouseholdFactsMock = vi.fn()
const confirmFactMutateAsync = vi.fn()

vi.mock('@/lib/hooks/useHousehold', () => ({
  useHouseholdSpending: (params?: { window?: string }) =>
    useHouseholdSpendingMock(params),
  useHouseholdFacts: () => useHouseholdFactsMock(),
  useConfirmFact: () => ({
    mutateAsync: confirmFactMutateAsync,
    isPending: false,
  }),
}))

const categories = [
  {
    category: 'Household',
    essentiality: 'mixed',
    totalSpend: 4446,
    averageMonthlySpend: 1482,
    shareOfSpend: 0.4,
    transactionCount: 30,
  },
  {
    category: 'Retail',
    essentiality: 'discretionary',
    totalSpend: 3861,
    averageMonthlySpend: 1287,
    shareOfSpend: 0.35,
    transactionCount: 22,
  },
  {
    category: 'Groceries',
    essentiality: 'essential',
    totalSpend: 738,
    averageMonthlySpend: 246,
    shareOfSpend: 0.08,
    transactionCount: 10,
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
      },
      categories,
      monthlyTrend: [],
      transactions: [],
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
    useHouseholdFactsMock.mockReturnValue({ data: [] })
    mockSpending()
  })

  it('reconciles top stats when rows only have found budgets', () => {
    render(<MoneyBudgetPanel />)

    expect(screen.getByText('Found budget total')).toBeInTheDocument()
    expect(screen.getByText('$2,750')).toBeInTheDocument()
    expect(
      screen.getByText('3 found rows not accepted yet.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Confirmed budget total')).toBeInTheDocument()
    expect(
      screen.getByText('Manual or accepted category caps.'),
    ).toBeInTheDocument()
    expect(screen.getByText('3 found · 0 confirmed.')).toBeInTheDocument()
    expect(screen.getByText('2 found · 0 confirmed.')).toBeInTheDocument()
    expect(screen.getAllByText('Found over budget')).toHaveLength(2)
    expect(screen.getByText('Found budget')).toBeInTheDocument()
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
      screen.getByText('2 found rows not accepted yet.'),
    ).toBeInTheDocument()
    expect(screen.getAllByText('$1,200')).not.toHaveLength(0)
    expect(screen.getByText('2 found · 1 confirmed.')).toBeInTheDocument()
    expect(screen.getByText('1 found · 1 confirmed.')).toBeInTheDocument()
    expect(screen.getByText('Accepted cap')).toBeInTheDocument()
    expect(screen.getAllByText('Over budget')).not.toHaveLength(0)
  })

  it('shows no-budget state when coverage is too thin to infer found values', () => {
    mockSpending(1)

    render(<MoneyBudgetPanel />)

    expect(
      screen.getByText('0 found rows not accepted yet.'),
    ).toBeInTheDocument()
    expect(screen.getAllByText('0 found · 0 confirmed.')).toHaveLength(2)
    expect(screen.getAllByText('Needs budget')).toHaveLength(3)
  })
})
