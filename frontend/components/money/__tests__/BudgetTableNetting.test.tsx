import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type {
  HouseholdBudgetVerdict,
  HouseholdSpendingCategory,
} from '@/lib/api/household'
import { BudgetTable } from '../BudgetTable'
import type { BudgetRowEntry } from '../useBudgetRows'

function entry(
  category: string,
  totalSpend: number,
  cap: number | null,
): BudgetRowEntry {
  const row = {
    category,
    essentiality: 'mixed',
    totalSpend,
    averageMonthlySpend: totalSpend,
    shareOfSpend: 0.1,
    transactionCount: 3,
    confirmedMonthlyBudget: cap,
    effectiveMonthlyBudget: cap,
    budgetVariance: cap == null ? null : totalSpend - cap,
  } as HouseholdSpendingCategory
  return {
    row,
    meta: undefined,
    foundBudget: null,
    currentBudget: cap,
    disabled: false,
    note: '',
  }
}

const verdict: HouseholdBudgetVerdict = {
  status: 'under_plan',
  headline: 'June 2026 came in $50 under your caps.',
  detail: '1 over by $200 · 1 under by $250.',
  capTotal: 1400,
  cappedActual: 1350,
  variance: -50,
  overTotal: 200,
  underTotal: 250,
  overCategoryCount: 1,
  underCategoryCount: 1,
  uncappedSpend: 0,
  uncappedCategoryCount: 0,
  largestOverCategory: 'Groceries',
  largestOverAmount: 200,
  largestUnderCategory: 'Gas',
  largestUnderAmount: 250,
}

function renderTable(verdictValue: HouseholdBudgetVerdict | null = verdict) {
  render(
    <BudgetTable
      isLoading={false}
      hasData
      activeRowCount={2}
      sortedActiveRows={[
        entry('Groceries', 1200, 1000),
        entry('Gas', 150, 400),
      ]}
      foundBudgetRowCount={0}
      verdict={verdictValue}
      hiddenCount={0}
      confirmPending={false}
      expandedCategory={null}
      categoryTransactionsFor={() => []}
      onAcceptAll={() => {}}
      setExpandedCategory={() => {}}
      onConfirmFound={() => {}}
      onSaveBudget={() => {}}
      transactionEditorProps={{
        categoryOptions: [],
        categorizePending: false,
        onCommitCategory: () => {},
      }}
    />,
  )
}

describe('BudgetTable netting footer', () => {
  it('nets the over and the under into one overall answer', () => {
    renderTable()

    expect(screen.getByText('$50 under overall')).toBeInTheDocument()
    expect(
      screen.getByText('$200 over in 1 · $250 under in 1'),
    ).toBeInTheDocument()
  })

  it('restates the server total rather than re-summing the rows', () => {
    // Rows sum to $1,350 against $1,400 of caps; the footer shows the verdict's
    // own figures, so the table cannot drift from the sentence above it.
    renderTable()

    expect(screen.getByText('$1,350')).toBeInTheDocument()
    expect(screen.getByText('$1,400')).toBeInTheDocument()
  })

  it('shows each row against the month, not against its run-rate', () => {
    renderTable()

    expect(screen.getByText('$200 over')).toBeInTheDocument()
    expect(screen.getByText('$250 under')).toBeInTheDocument()
  })

  it('drops the footer entirely when no cap is in force', () => {
    renderTable(null)

    expect(screen.queryByText(/overall/)).not.toBeInTheDocument()
  })
})
