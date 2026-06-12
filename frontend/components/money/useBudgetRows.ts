import { useMemo } from 'react'
import {
  type CategoryBudgetMeta,
  categoryBudgetMetaMap,
} from '@/components/money/household-fact-metadata'
import { aggregateMerchants } from '@/components/money/merchant-aggregation'
import type {
  HouseholdConfirmedFact,
  HouseholdSpendingCategory,
  HouseholdSpendingTransaction,
  HouseholdSpendingView,
} from '@/lib/api/household'
import { trendColors, trendKey } from './budget-helpers'
import { buildCategoryOptions } from './category-options'

// Plot at most the top spenders so the chart stays legible; clicking a legend chip
// isolates that one series and overlays its cap.
export const TREND_TOP_N = 8

export type BudgetRowEntry = {
  row: HouseholdSpendingCategory
  meta: CategoryBudgetMeta | undefined
  foundBudget: number | null
  currentBudget: number | null
  disabled: boolean
  note: string
}

export function entryBreach(entry: BudgetRowEntry) {
  const cap = entry.currentBudget ?? entry.foundBudget
  if (cap == null || cap <= 0) {
    return { isOver: false, overAmount: 0 }
  }
  const over = entry.row.averageMonthlySpend - cap
  return { isOver: over > 0, overAmount: Math.max(over, 0) }
}

export interface UseBudgetRowsInput {
  spending: HouseholdSpendingView | undefined
  facts: HouseholdConfirmedFact[]
  isolatedSeries: string | null
}

/**
 * Derive every budget collection the panel renders — sorted rows, summary
 * totals, trendline series, and merchant aggregates — from the raw spending
 * payload and confirmed facts. Pulling this out of the panel keeps the render
 * tree thin while preserving the exact server-trusting math.
 */
export function useBudgetRows({
  spending,
  facts,
  isolatedSeries,
}: UseBudgetRowsInput) {
  const budgetMeta = useMemo(() => categoryBudgetMetaMap(facts), [facts])
  const coverageMonths = spending?.summary.coverageMonths ?? 0

  const rows = useMemo(() => {
    return (spending?.categories ?? [])
      .map((row) => {
        const meta = budgetMeta.get(row.category)
        // Trust the server's suggested cap; never recompute it client-side (the
        // rounding rules differ between JS and Python and would silently drift).
        const foundBudget = row.foundMonthlyBudget ?? null
        return {
          row,
          meta,
          foundBudget,
          currentBudget:
            row.confirmedMonthlyBudget ?? meta?.monthlyTarget ?? null,
          disabled: row.budgetDisabled ?? meta?.disabled === true,
          note: row.budgetNote ?? meta?.note ?? '',
        }
      })
      .sort(
        (left, right) =>
          right.row.averageMonthlySpend - left.row.averageMonthlySpend,
      )
  }, [budgetMeta, coverageMonths, spending?.categories])

  const categoryOptions = useMemo(
    () =>
      buildCategoryOptions([
        ...(spending?.categories ?? []).map((row) => row.category),
        ...(spending?.transactions ?? []).map((row) => row.category),
      ]),
    [spending?.categories, spending?.transactions],
  )

  const transactionsByCategory = useMemo(() => {
    const map = new Map<string, HouseholdSpendingTransaction[]>()
    for (const transaction of spending?.transactions ?? []) {
      const category = transaction.category || 'Unknown'
      const bucket = map.get(category) ?? []
      bucket.push(transaction)
      map.set(category, bucket)
    }
    for (const bucket of map.values()) {
      bucket.sort((left, right) => right.date.localeCompare(left.date))
    }
    return map
  }, [spending?.transactions])

  const merchantAggregates = useMemo(
    () => aggregateMerchants(spending?.transactions),
    [spending?.transactions],
  )

  const activeRows = rows.filter((entry) => entry.disabled !== true)
  const hiddenRows = rows.filter((entry) => entry.disabled === true)

  // Breached categories sort to the top, most-over first, so over-budget is not a
  // dead number buried in a spend-ordered list.
  const sortedActiveRows = [...activeRows].sort((left, right) => {
    const leftBreach = entryBreach(left)
    const rightBreach = entryBreach(right)
    if (leftBreach.isOver !== rightBreach.isOver) {
      return leftBreach.isOver ? -1 : 1
    }
    if (leftBreach.isOver && rightBreach.isOver) {
      return rightBreach.overAmount - leftBreach.overAmount
    }
    return right.row.averageMonthlySpend - left.row.averageMonthlySpend
  })
  const confirmedBudgetRows = activeRows.filter(
    (entry) => entry.currentBudget != null,
  )
  const foundBudgetRows = activeRows.filter(
    (entry) => entry.currentBudget == null && entry.foundBudget != null,
  )

  // The backend owns every summary number the user reads; `?? 0` only covers
  // the loading state (no payload yet) and must never become a row-math fallback.
  const summary = spending?.summary
  const foundBudgetTotal = summary?.foundBudgetTotal ?? 0
  const confirmedBudgetTotal = summary?.confirmedBudgetTotal ?? 0
  const foundBudgetCategoryCount = summary?.foundBudgetCategoryCount ?? 0
  const confirmedBudgetCategoryCount =
    summary?.confirmedBudgetCategoryCount ?? 0
  const budgetedCategoryCount = summary?.budgetedCategoryCount ?? 0
  const foundOverBudgetCount = summary?.foundOverBudgetCount ?? 0
  const confirmedOverBudgetCount = summary?.confirmedOverBudgetCount ?? 0
  const overBudgetCount = summary?.overBudgetCount ?? 0
  const unknownTransactions = transactionsByCategory.get('Unknown') ?? []
  const unknownSpend = unknownTransactions.reduce(
    (sum, transaction) => sum + transaction.amount,
    0,
  )

  const trendMeta = useMemo(() => {
    const keyByCategory = new Map<string, string>()
    const categories = activeRows.map((entry) => entry.row.category)
    categories.forEach((category, index) => {
      keyByCategory.set(category, trendKey(category, index))
    })
    const chartRows = new Map<string, Record<string, string | number>>()
    for (const point of spending?.categoryMonthlyTrend ?? []) {
      const key = keyByCategory.get(point.category)
      if (!key) {
        continue
      }
      const row = chartRows.get(point.month) ?? { month: point.month }
      row[key] = point.totalSpend
      chartRows.set(point.month, row)
    }
    return {
      categories: categories.map((category, index) => ({
        category,
        key: keyByCategory.get(category) ?? trendKey(category, index),
        color: trendColors[index % trendColors.length],
      })),
      data: Array.from(chartRows.values()).sort((left, right) =>
        String(left.month).localeCompare(String(right.month)),
      ),
    }
  }, [activeRows, spending?.categoryMonthlyTrend])

  const chartCategories = isolatedSeries
    ? trendMeta.categories.filter((entry) => entry.category === isolatedSeries)
    : trendMeta.categories.slice(0, TREND_TOP_N)
  const isolatedCap = isolatedSeries
    ? (() => {
        const entry = activeRows.find(
          (item) => item.row.category === isolatedSeries,
        )
        return entry ? (entry.currentBudget ?? entry.foundBudget) : null
      })()
    : null

  return {
    budgetMeta,
    rows,
    categoryOptions,
    transactionsByCategory,
    merchantAggregates,
    activeRows,
    hiddenRows,
    sortedActiveRows,
    confirmedBudgetRows,
    foundBudgetRows,
    foundBudgetTotal,
    confirmedBudgetTotal,
    foundBudgetCategoryCount,
    confirmedBudgetCategoryCount,
    budgetedCategoryCount,
    foundOverBudgetCount,
    confirmedOverBudgetCount,
    overBudgetCount,
    unknownTransactions,
    unknownSpend,
    trendMeta,
    chartCategories,
    isolatedCap,
  }
}
