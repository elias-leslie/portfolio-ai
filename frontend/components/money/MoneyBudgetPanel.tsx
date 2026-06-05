'use client'

import { ChevronDown, ChevronRight } from 'lucide-react'
import { Fragment, useEffect, useMemo, useState } from 'react'
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  type TooltipProps,
  type TooltipValueType,
  XAxis,
  YAxis,
} from 'recharts'
import {
  CATEGORY_BUDGET_PREFIX,
  categoryBudgetMetaMap,
  serializeCategoryBudgetMeta,
} from '@/components/money/household-fact-metadata'
import { aggregateMerchants } from '@/components/money/merchant-aggregation'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import type {
  HouseholdSpendingCategory,
  HouseholdSpendingTransaction,
} from '@/lib/api/household'
import {
  formatCurrency,
  formatCurrencyWhole,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import {
  useCategorizeHouseholdTransaction,
  useConfirmFact,
  useHouseholdFacts,
  useHouseholdSpending,
} from '@/lib/hooks/useHousehold'
import { cn } from '@/lib/utils'

type BudgetWindow = '1m' | '3m' | '6m'

const budgetWindows: Array<{ value: BudgetWindow; label: string }> = [
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '6m', label: '6M' },
]

const CATEGORY_OPTIONS = [
  'Unknown',
  'Bills',
  'Dining',
  'Donations',
  'Education',
  'Entertainment',
  'Fitness',
  'Gas',
  'Groceries',
  'Healthcare',
  'Home',
  'Household',
  'Insurance',
  'Personal Care',
  'Retail',
  'Subscriptions',
  'Transportation',
  'Travel',
]

const trendColors = [
  'var(--color-chart-1)',
  'var(--color-chart-2)',
  'var(--color-chart-3)',
  'var(--color-chart-4)',
  'var(--color-chart-5)',
  'var(--color-chart-blue)',
  'var(--color-chart-cyan)',
  'var(--color-chart-orange)',
]

type RecategorizeDraft = {
  transactionId: string
  category: string
  essentiality: string
  applyToMerchant: boolean
}

function budgetStatus(
  currentBudget: number | null,
  foundBudget: number | null,
  actual: number,
) {
  if (currentBudget != null) {
    return {
      label: actual > currentBudget ? 'Over confirmed cap' : 'Confirmed cap',
      variant:
        actual > currentBudget ? ('warning' as const) : ('success' as const),
    }
  }
  if (foundBudget != null) {
    return {
      label: actual > foundBudget ? 'Over suggested cap' : 'Suggested cap',
      variant:
        actual > foundBudget ? ('warning' as const) : ('outline' as const),
    }
  }
  return {
    label: 'No cap yet',
    variant: 'secondary' as const,
  }
}

function formatBudgetDate(value: string) {
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date)
}

function formatMonthLabel(value: string) {
  const date = new Date(`${value}-01T00:00:00`)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString('en-US', {
    month: 'short',
    year: '2-digit',
  })
}

function formatThousandsAxis(value: number) {
  if (Math.abs(value) < 1000) {
    return `$${Math.round(value)}`
  }
  const thousands = value / 1000
  return `$${Number.isInteger(thousands) ? thousands.toFixed(0) : thousands.toFixed(1)}k`
}

function tooltipNumber(value: TooltipValueType | undefined): number | null {
  if (typeof value === 'number') {
    return value
  }
  if (typeof value === 'string') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  if (Array.isArray(value)) {
    const parsed = Number(value[0])
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

const currencyTooltipFormatter: TooltipProps<TooltipValueType>['formatter'] = (
  value,
  name,
) => [
  formatCurrency(tooltipNumber(value), { decimals: 0, nullDisplay: '—' }),
  String(name),
]

const monthTooltipLabelFormatter: TooltipProps<TooltipValueType>['labelFormatter'] =
  (label) =>
    formatMonthLabel(typeof label === 'string' ? label : String(label ?? ''))

function trendKey(category: string, index: number) {
  const slug = category
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return `category_${slug || 'unknown'}_${index}`
}

export function MoneyBudgetPanel() {
  const [window, setWindow] = useState<BudgetWindow>('3m')
  const [selectedCategory, setSelectedCategory] =
    useState<HouseholdSpendingCategory | null>(null)
  const [budgetInput, setBudgetInput] = useState('')
  const [noteInput, setNoteInput] = useState('')
  const [disabled, setDisabled] = useState(false)
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null)
  const [recategorizeDraft, setRecategorizeDraft] =
    useState<RecategorizeDraft | null>(null)
  const [categoryPickerOpenFor, setCategoryPickerOpenFor] = useState<
    string | null
  >(null)
  const [isolatedSeries, setIsolatedSeries] = useState<string | null>(null)
  const {
    data: spending,
    error,
    refetch,
    isFetching,
    isLoading,
  } = useHouseholdSpending({ window })
  const { data: facts = [] } = useHouseholdFacts()
  const confirmFact = useConfirmFact()
  const categorizeTransaction = useCategorizeHouseholdTransaction()

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

  const categoryOptions = useMemo(() => {
    const categories = new Set(CATEGORY_OPTIONS)
    for (const row of spending?.categories ?? []) {
      categories.add(row.category)
    }
    for (const row of spending?.transactions ?? []) {
      categories.add(row.category)
    }
    return Array.from(categories).sort((left, right) =>
      left === 'Unknown'
        ? -1
        : right === 'Unknown'
          ? 1
          : left.localeCompare(right),
    )
  }, [spending?.categories, spending?.transactions])

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

  function entryBreach(entry: (typeof rows)[number]) {
    const cap = entry.currentBudget ?? entry.foundBudget
    if (cap == null || cap <= 0) {
      return { isOver: false, overAmount: 0 }
    }
    const over = entry.row.averageMonthlySpend - cap
    return { isOver: over > 0, overAmount: Math.max(over, 0) }
  }

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

  const computedConfirmedBudgetTotal = confirmedBudgetRows.reduce(
    (sum, entry) => sum + (entry.currentBudget ?? 0),
    0,
  )
  const computedFoundBudgetTotal = foundBudgetRows.reduce(
    (sum, entry) => sum + (entry.foundBudget ?? 0),
    0,
  )
  const computedConfirmedOverBudgetCount = confirmedBudgetRows.filter(
    (entry) =>
      entry.currentBudget != null &&
      entry.row.averageMonthlySpend > entry.currentBudget,
  ).length
  const computedFoundOverBudgetCount = foundBudgetRows.filter(
    (entry) =>
      entry.foundBudget != null &&
      entry.row.averageMonthlySpend > entry.foundBudget,
  ).length
  const computedBudgetedCategoryCount =
    confirmedBudgetRows.length + foundBudgetRows.length
  const foundBudgetTotal =
    spending?.summary.foundBudgetTotal ?? computedFoundBudgetTotal
  const confirmedBudgetTotal =
    spending?.summary.confirmedBudgetTotal ?? computedConfirmedBudgetTotal
  const foundBudgetCategoryCount =
    spending?.summary.foundBudgetCategoryCount ?? foundBudgetRows.length
  const confirmedBudgetCategoryCount =
    spending?.summary.confirmedBudgetCategoryCount ?? confirmedBudgetRows.length
  const budgetedCategoryCount =
    spending?.summary.budgetedCategoryCount ?? computedBudgetedCategoryCount
  const foundOverBudgetCount =
    spending?.summary.foundOverBudgetCount ?? computedFoundOverBudgetCount
  const confirmedOverBudgetCount =
    spending?.summary.confirmedOverBudgetCount ??
    computedConfirmedOverBudgetCount
  const overBudgetCount =
    spending?.summary.overBudgetCount ??
    foundOverBudgetCount + confirmedOverBudgetCount
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

  // Plot at most the top spenders so the chart stays legible; clicking a legend chip
  // isolates that one series and overlays its cap.
  const TREND_TOP_N = 8
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

  async function acceptAllSuggestedCaps() {
    for (const entry of foundBudgetRows) {
      if (entry.foundBudget == null) {
        continue
      }
      await confirmFact.mutateAsync({
        factKey: `${CATEGORY_BUDGET_PREFIX}${entry.row.category}`,
        factValue: serializeCategoryBudgetMeta({
          category: entry.row.category,
          note: entry.meta?.note ?? '',
          disabled: false,
          monthlyTarget: entry.foundBudget,
          source: 'accepted',
        }),
      })
    }
  }

  function startRecategorize(transaction: HouseholdSpendingTransaction) {
    setRecategorizeDraft({
      transactionId: transaction.id,
      category: transaction.category || 'Unknown',
      essentiality: transaction.essentiality || 'mixed',
      applyToMerchant: transaction.category === 'Unknown',
    })
    setCategoryPickerOpenFor(transaction.id)
  }

  async function saveRecategorize(transaction: HouseholdSpendingTransaction) {
    if (!recategorizeDraft || !recategorizeDraft.category.trim()) {
      return
    }
    await categorizeTransaction.mutateAsync({
      transactionId: transaction.id,
      category: recategorizeDraft.category.trim(),
      essentiality: recategorizeDraft.essentiality,
      applyToMerchant: recategorizeDraft.applyToMerchant,
    })
    setRecategorizeDraft(null)
    setCategoryPickerOpenFor(null)
  }

  function renderTransactionEditor(transaction: HouseholdSpendingTransaction) {
    const isEditing = recategorizeDraft?.transactionId === transaction.id
    const isCategoryPickerOpen = categoryPickerOpenFor === transaction.id
    const categoryListId = `category-options-${transaction.id}`
    const merchantKey = transaction.merchant.trim().toLowerCase()
    const similarMerchantCount =
      merchantAggregates.get(merchantKey)?.transactionCount ?? 1

    return (
      <div
        key={transaction.id}
        className="grid gap-3 border-b border-border/20 px-4 py-3 last:border-b-0 lg:grid-cols-[1fr_auto]"
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium text-text">{transaction.merchant}</p>
            {transaction.needsCategoryReview ||
            transaction.category === 'Unknown' ? (
              <Badge variant="warning">Needs category</Badge>
            ) : null}
          </div>
          <p className="mt-1 text-xs text-text-muted">
            {formatBudgetDate(transaction.date)} ·{' '}
            {transaction.accountLabel ?? 'No account'} ·{' '}
            {transaction.description}
          </p>
          {!isEditing ? (
            <p className="mt-2 text-xs text-text-muted">
              {transaction.category} ·{' '}
              {formatEnumLabel(transaction.essentiality)}
              {transaction.categoryConfidence != null
                ? ` · ${(transaction.categoryConfidence * 100).toFixed(0)}% confidence`
                : ''}
            </p>
          ) : null}
        </div>

        <div className="flex min-w-[280px] flex-col gap-3 lg:items-end">
          <p className="text-right font-mono tabular-nums text-text">
            {formatCurrency(transaction.amount, { decimals: 2 })}
          </p>
          {isEditing && recategorizeDraft ? (
            <div className="w-full space-y-3 rounded-xl border border-border/35 bg-surface-muted/15 p-3 lg:w-[420px]">
              <div className="grid gap-3 sm:grid-cols-[1fr_150px]">
                <div
                  className="relative space-y-1.5"
                  onBlur={(event) => {
                    const nextFocus = event.relatedTarget
                    if (
                      nextFocus instanceof Node &&
                      event.currentTarget.contains(nextFocus)
                    ) {
                      return
                    }
                    setCategoryPickerOpenFor((current) =>
                      current === transaction.id ? null : current,
                    )
                  }}
                >
                  <Label htmlFor={`category-${transaction.id}`}>Category</Label>
                  <div className="relative">
                    <Input
                      id={`category-${transaction.id}`}
                      value={recategorizeDraft.category}
                      role="combobox"
                      aria-expanded={isCategoryPickerOpen}
                      aria-controls={categoryListId}
                      aria-autocomplete="list"
                      className="pr-10"
                      onFocus={() => setCategoryPickerOpenFor(transaction.id)}
                      onClick={() => setCategoryPickerOpenFor(transaction.id)}
                      onChange={(event) => {
                        setRecategorizeDraft((current) =>
                          current
                            ? { ...current, category: event.target.value }
                            : current,
                        )
                        setCategoryPickerOpenFor(transaction.id)
                      }}
                    />
                    <button
                      type="button"
                      aria-label="Show category options"
                      aria-expanded={isCategoryPickerOpen}
                      aria-controls={categoryListId}
                      className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-md text-text-muted transition-colors hover:text-text"
                      onClick={() =>
                        setCategoryPickerOpenFor((current) =>
                          current === transaction.id ? null : transaction.id,
                        )
                      }
                    >
                      <ChevronDown className="h-4 w-4" />
                    </button>
                  </div>
                  {isCategoryPickerOpen ? (
                    <div
                      id={categoryListId}
                      role="listbox"
                      aria-label="Existing categories"
                      className="absolute left-0 right-0 top-full z-50 mt-1 max-h-64 overflow-auto rounded-xl border border-border/50 bg-surface p-1 shadow-xl"
                    >
                      {categoryOptions.map((category) => (
                        <button
                          key={category}
                          type="button"
                          role="option"
                          aria-selected={
                            category === recategorizeDraft.category
                          }
                          className={cn(
                            'flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm text-text transition-colors hover:bg-surface-muted/70',
                            category === recategorizeDraft.category &&
                              'bg-primary/15 text-primary',
                          )}
                          onClick={() => {
                            setRecategorizeDraft((current) =>
                              current ? { ...current, category } : current,
                            )
                            setCategoryPickerOpenFor(null)
                          }}
                        >
                          <span>{category}</span>
                          {category === recategorizeDraft.category ? (
                            <span className="text-xs font-medium">
                              Selected
                            </span>
                          ) : null}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
                <div className="space-y-1.5">
                  <Label>Type</Label>
                  <Select
                    value={recategorizeDraft.essentiality}
                    onValueChange={(value) =>
                      setRecategorizeDraft((current) =>
                        current ? { ...current, essentiality: value } : current,
                      )
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="essential">Essential</SelectItem>
                      <SelectItem value="mixed">Mixed</SelectItem>
                      <SelectItem value="discretionary">
                        Discretionary
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <label className="flex items-start gap-2 text-sm text-text-muted">
                <Checkbox
                  checked={recategorizeDraft.applyToMerchant}
                  onCheckedChange={(checked) =>
                    setRecategorizeDraft((current) =>
                      current
                        ? {
                            ...current,
                            applyToMerchant: checked === true,
                          }
                        : current,
                    )
                  }
                />
                <span>
                  Apply to this merchant going forward
                  {similarMerchantCount > 1
                    ? ` and update ${similarMerchantCount} matching purchases`
                    : ''}
                  .
                </span>
              </label>
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setRecategorizeDraft(null)
                    setCategoryPickerOpenFor(null)
                  }}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => void saveRecategorize(transaction)}
                  disabled={
                    categorizeTransaction.isPending ||
                    !recategorizeDraft.category.trim()
                  }
                >
                  {categorizeTransaction.isPending ? 'Saving...' : 'Save'}
                </Button>
              </div>
            </div>
          ) : (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => startRecategorize(transaction)}
            >
              Categorize
            </Button>
          )}
        </div>
      </div>
    )
  }

  function renderBudgetRow(entry: (typeof activeRows)[number]) {
    const { row, meta, currentBudget, foundBudget, note } = entry
    const status = budgetStatus(
      currentBudget,
      foundBudget,
      row.averageMonthlySpend,
    )
    const isExpanded = expandedCategory === row.category
    const categoryTransactions = transactionsByCategory.get(row.category) ?? []

    return (
      <Fragment key={row.category}>
        <tr
          className={cn(
            'hover:bg-surface-muted/10',
            isExpanded && 'bg-primary/10',
          )}
        >
          <td className="border-b border-border/20 px-4 py-3 font-medium text-text">
            <button
              type="button"
              onClick={() =>
                setExpandedCategory((current) =>
                  current === row.category ? null : row.category,
                )
              }
              className="flex items-center gap-2 text-left"
              aria-expanded={isExpanded}
            >
              {isExpanded ? (
                <ChevronDown className="h-4 w-4 text-text-muted" />
              ) : (
                <ChevronRight className="h-4 w-4 text-text-muted" />
              )}
              <span>{row.category}</span>
              {row.category === 'Unknown' ? (
                <Badge variant="warning">Review</Badge>
              ) : null}
            </button>
          </td>
          <td className="border-b border-border/20 px-4 py-3">
            <Badge variant="outline">{formatEnumLabel(row.essentiality)}</Badge>
          </td>
          <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
            {formatCurrency(row.averageMonthlySpend, {
              decimals: 0,
            })}
          </td>
          <td className="border-b border-border/20 px-4 py-3 text-right font-mono tabular-nums text-text">
            {currentBudget != null ? (
              <span>{formatCurrency(currentBudget, { decimals: 0 })}</span>
            ) : foundBudget != null ? (
              <span className="text-text-muted">
                ~{formatCurrency(foundBudget, { decimals: 0 })}
                <span className="ml-1 text-[10px] uppercase tracking-wide">
                  suggested
                </span>
              </span>
            ) : (
              '—'
            )}
          </td>
          <td className="border-b border-border/20 px-4 py-3">
            <Badge variant={status.variant}>{status.label}</Badge>
            {entryBreach(entry).isOver ? (
              <div className="mt-1 text-xs font-medium text-warning">
                {formatCurrency(entryBreach(entry).overAmount, { decimals: 0 })}
                /mo over
              </div>
            ) : null}
          </td>
          <td className="border-b border-border/20 px-4 py-3 text-text-muted">
            {note ? note : '—'}
          </td>
          <td className="border-b border-border/20 px-4 py-3 text-right">
            <div className="flex justify-end gap-2">
              {currentBudget == null && foundBudget != null ? (
                <Button
                  type="button"
                  size="sm"
                  onClick={() =>
                    void confirmFact.mutateAsync({
                      factKey: `${CATEGORY_BUDGET_PREFIX}${row.category}`,
                      factValue: serializeCategoryBudgetMeta({
                        category: row.category,
                        note: meta?.note ?? '',
                        disabled: false,
                        monthlyTarget: foundBudget,
                        source: 'accepted',
                      }),
                    })
                  }
                  disabled={confirmFact.isPending}
                >
                  Accept
                </Button>
              ) : null}
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => setSelectedCategory(row)}
              >
                Budget
              </Button>
            </div>
          </td>
        </tr>
        {isExpanded ? (
          <tr>
            <td colSpan={7} className="border-b border-border/30 p-0">
              <div className="bg-surface-muted/10">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/20 px-4 py-3">
                  <div>
                    <p className="text-sm font-semibold text-text">
                      {categoryTransactions.length} purchase
                      {categoryTransactions.length === 1 ? '' : 's'} in{' '}
                      {row.category}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      Recategorize one row, or apply a merchant rule so matching
                      purchases update automatically going forward.
                    </p>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setExpandedCategory(null)}
                  >
                    Collapse
                  </Button>
                </div>
                {categoryTransactions.length === 0 ? (
                  <p className="px-4 py-6 text-sm text-text-muted">
                    No purchases are visible for this category in the selected
                    window.
                  </p>
                ) : (
                  <div className="max-h-[560px] overflow-auto">
                    {categoryTransactions.map(renderTransactionEditor)}
                  </div>
                )}
              </div>
            </td>
          </tr>
        ) : null}
      </Fragment>
    )
  }

  useEffect(() => {
    if (!selectedCategory) {
      setBudgetInput('')
      setNoteInput('')
      setDisabled(false)
      return
    }
    const meta = budgetMeta.get(selectedCategory.category)
    setBudgetInput(
      meta?.monthlyTarget != null ? String(meta.monthlyTarget) : '',
    )
    setNoteInput(meta?.note ?? '')
    setDisabled(meta?.disabled === true)
  }, [budgetMeta, selectedCategory])

  useEffect(() => {
    if (
      expandedCategory &&
      !activeRows.some((entry) => entry.row.category === expandedCategory)
    ) {
      setExpandedCategory(null)
    }
    if (
      recategorizeDraft &&
      !spending?.transactions.some(
        (transaction) => transaction.id === recategorizeDraft.transactionId,
      )
    ) {
      setRecategorizeDraft(null)
      setCategoryPickerOpenFor(null)
    }
  }, [activeRows, expandedCategory, recategorizeDraft, spending?.transactions])

  async function saveSelectedCategory(
    source: 'manual' | 'accepted',
    overrideBudget?: number | null,
  ) {
    if (!selectedCategory) {
      return
    }
    const parsedBudget =
      overrideBudget !== undefined
        ? overrideBudget
        : budgetInput.trim()
          ? Number(budgetInput.trim())
          : null
    if (
      budgetInput.trim() &&
      overrideBudget === undefined &&
      (!Number.isFinite(parsedBudget) || parsedBudget == null)
    ) {
      return
    }
    if (disabled && !noteInput.trim()) {
      return
    }
    await confirmFact.mutateAsync({
      factKey: `${CATEGORY_BUDGET_PREFIX}${selectedCategory.category}`,
      factValue: serializeCategoryBudgetMeta({
        category: selectedCategory.category,
        note: noteInput.trim(),
        disabled,
        monthlyTarget: parsedBudget,
        source,
      }),
    })
    setSelectedCategory(null)
  }

  if (error) {
    return (
      <SectionCard
        variant="surface"
        title="Budget"
        description="Failed to load category budgets."
      >
        <Button onClick={() => void refetch()} disabled={isFetching}>
          Retry budget
        </Button>
      </SectionCard>
    )
  }

  return (
    <div className="space-y-6">
      <SectionCard
        variant="surface"
        title="Budget"
        description="Set category caps where they matter. Suggested caps stay separate until you accept them or replace them yourself."
        actions={
          <div className="flex flex-wrap gap-2">
            {budgetWindows.map((option) => (
              <Button
                key={option.value}
                type="button"
                size="sm"
                variant={window === option.value ? 'default' : 'outline'}
                onClick={() => setWindow(option.value)}
              >
                {option.label}
              </Button>
            ))}
          </div>
        }
      >
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Observed monthly spend
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {formatCurrencyWhole(spending?.summary.averageMonthlySpend)}
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Suggested cap total
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {formatCurrencyWhole(foundBudgetTotal)}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {foundBudgetCategoryCount} suggested row
              {foundBudgetCategoryCount === 1 ? '' : 's'} not accepted yet.
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Confirmed cap total
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {formatCurrencyWhole(confirmedBudgetTotal)}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Manual or accepted category caps.
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Unknown purchases
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {unknownTransactions.length}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              purchase{unknownTransactions.length === 1 ? '' : 's'} to
              categorize · {formatCurrencyWhole(unknownSpend)}
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Budgeted categories
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {budgetedCategoryCount}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {foundBudgetCategoryCount} suggested ·{' '}
              {confirmedBudgetCategoryCount} confirmed.
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Over budget
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {overBudgetCount}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {foundOverBudgetCount} suggested · {confirmedOverBudgetCount}{' '}
              confirmed.
            </p>
          </div>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Monthly income
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {formatCurrencyWhole(spending?.summary.averageMonthlyIncome)}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Tracked inflow, averaged.
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Net cash flow
            </p>
            <p
              className={cn(
                'mt-3 text-2xl font-semibold',
                (spending?.summary.netCashFlow ?? 0) >= 0
                  ? 'text-gain'
                  : 'text-loss',
              )}
            >
              {formatCurrencyWhole(spending?.summary.netCashFlow)}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Income minus tracked spend, this window.
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Savings rate
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {spending?.summary.savingsRate != null
                ? formatPercent(spending.summary.savingsRate * 100, {
                    decimals: 0,
                  })
                : '—'}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Share of income not spent.
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Month-to-date spend
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {formatCurrencyWhole(spending?.summary.monthToDateSpend)}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              Spent so far this calendar month.
            </p>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Category trendlines"
        description={`Monthly spend by category for ${spending?.summary.timeframeLabel ?? 'the selected window'}. Every visible budget category is plotted in one chart.`}
      >
        {trendMeta.data.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/20 px-6 py-10 text-sm text-text-muted">
            No category trendline is available for this window yet.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="h-80">
              <ResponsiveContainer
                width="100%"
                height="100%"
                minWidth={240}
                minHeight={320}
                initialDimension={{ width: 720, height: 320 }}
              >
                <LineChart
                  data={trendMeta.data}
                  margin={{ top: 12, right: 16, left: 0, bottom: 8 }}
                >
                  <XAxis
                    dataKey="month"
                    tickFormatter={formatMonthLabel}
                    tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                    axisLine={{ stroke: 'var(--color-border)' }}
                    tickLine={false}
                  />
                  <YAxis
                    tickFormatter={formatThousandsAxis}
                    tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                    axisLine={false}
                    tickLine={false}
                    width={44}
                  />
                  <Tooltip
                    formatter={currencyTooltipFormatter}
                    labelFormatter={monthTooltipLabelFormatter}
                  />
                  {isolatedCap != null ? (
                    <ReferenceLine
                      y={isolatedCap}
                      stroke="var(--color-warning)"
                      strokeDasharray="4 4"
                      label={{
                        value: `Cap ${formatCurrency(isolatedCap, { decimals: 0 })}`,
                        position: 'insideTopRight',
                        fontSize: 10,
                        fill: 'var(--color-warning)',
                      }}
                    />
                  ) : null}
                  {chartCategories.map((entry) => (
                    <Line
                      key={entry.key}
                      type="monotone"
                      dataKey={entry.key}
                      name={entry.category}
                      stroke={entry.color}
                      strokeWidth={entry.category === 'Unknown' ? 3 : 2}
                      dot={false}
                      activeDot={{ r: 4 }}
                      connectNulls
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="flex max-h-28 flex-wrap items-center gap-x-4 gap-y-2 overflow-auto text-xs text-text-muted">
              {!isolatedSeries && trendMeta.categories.length > TREND_TOP_N ? (
                <span className="text-text-muted/70">
                  Showing top {TREND_TOP_N} of {trendMeta.categories.length} —
                  click a category to isolate it:
                </span>
              ) : null}
              {isolatedSeries ? (
                <button
                  type="button"
                  onClick={() => setIsolatedSeries(null)}
                  className="rounded-full border border-border/40 px-2 py-0.5 font-medium text-text hover:border-primary/40"
                >
                  ← Show top {TREND_TOP_N}
                </button>
              ) : null}
              {trendMeta.categories.map((entry) => (
                <button
                  type="button"
                  key={entry.key}
                  onClick={() =>
                    setIsolatedSeries((current) =>
                      current === entry.category ? null : entry.category,
                    )
                  }
                  className={cn(
                    'inline-flex items-center gap-2 rounded-full px-2 py-0.5 transition-colors hover:text-text',
                    isolatedSeries === entry.category &&
                      'bg-surface-muted/40 text-text',
                  )}
                >
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: entry.color }}
                  />
                  {entry.category}
                </button>
              ))}
            </div>
          </div>
        )}
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Category budgets"
        description="Expand a category to inspect the purchases behind it, correct wrong categories, or create merchant rules."
        padding="none"
        className="overflow-hidden"
        actions={
          foundBudgetRows.length > 0 ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => void acceptAllSuggestedCaps()}
              disabled={confirmFact.isPending}
            >
              Accept all {foundBudgetRows.length} suggested cap
              {foundBudgetRows.length === 1 ? '' : 's'}
            </Button>
          ) : null
        }
      >
        <div className="overflow-auto">
          <table className="w-full min-w-[880px] border-separate border-spacing-0 text-sm">
            <thead className="bg-bg/95 backdrop-blur">
              <tr>
                <th className="border-b border-border/35 px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Category
                </th>
                <th className="border-b border-border/35 px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Type
                </th>
                <th className="border-b border-border/35 px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Observed / mo
                </th>
                <th className="border-b border-border/35 px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Budget
                </th>
                <th className="border-b border-border/35 px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Status
                </th>
                <th className="border-b border-border/35 px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Note
                </th>
                <th className="border-b border-border/35 px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                  Action
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading && !spending ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-10 text-center text-sm text-text-muted"
                  >
                    Loading category budgets...
                  </td>
                </tr>
              ) : activeRows.length === 0 ? (
                <tr>
                  <td
                    colSpan={7}
                    className="px-4 py-10 text-center text-sm text-text-muted"
                  >
                    No budgetable categories are visible yet.
                  </td>
                </tr>
              ) : (
                sortedActiveRows.map(renderBudgetRow)
              )}
            </tbody>
          </table>
        </div>
      </SectionCard>

      {hiddenRows.length > 0 ? (
        <SectionCard
          variant="surface"
          title="Hidden categories"
          description="Disabled categories stay out of the main budget table until you re-enable them."
        >
          <div className="flex flex-wrap gap-2">
            {hiddenRows.map(({ row, note }) => (
              <button
                key={row.category}
                type="button"
                onClick={() => setSelectedCategory(row)}
                className="rounded-full border border-border/35 bg-surface-muted/20 px-3 py-2 text-sm text-text transition-colors hover:border-border/60"
              >
                {row.category}
                {note ? ` · ${note}` : ''}
              </button>
            ))}
          </div>
        </SectionCard>
      ) : null}

      <Dialog
        open={selectedCategory != null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedCategory(null)
          }
        }}
      >
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {selectedCategory
                ? `${selectedCategory.category} budget`
                : 'Budget'}
            </DialogTitle>
            <DialogDescription>
              Save a manual cap, accept a suggested cap, add context for Jenny,
              or hide the category when it should stay out of the budget view.
            </DialogDescription>
          </DialogHeader>

          {selectedCategory ? (
            <div className="space-y-5">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                    Observed monthly spend
                  </p>
                  <p className="mt-3 text-xl font-semibold text-text">
                    {formatCurrency(selectedCategory.averageMonthlySpend, {
                      decimals: 0,
                    })}
                  </p>
                </div>
                <div className="rounded-2xl border border-warning/30 bg-warning/8 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-warning">
                    Suggested cap
                  </p>
                  <p className="mt-3 text-xl font-semibold text-text">
                    {formatCurrency(
                      selectedCategory.foundMonthlyBudget ?? null,
                      {
                        decimals: 0,
                      },
                    )}
                  </p>
                  <p className="mt-2 text-sm text-text-muted">
                    Derived from recent transaction evidence.
                  </p>
                </div>
                <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
                    Type
                  </p>
                  <p className="mt-3 text-xl font-semibold text-text">
                    {formatEnumLabel(selectedCategory.essentiality)}
                  </p>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-[0.8fr_1.2fr]">
                <div className="space-y-2">
                  <Label htmlFor="category-budget-input">Monthly budget</Label>
                  <Input
                    id="category-budget-input"
                    inputMode="decimal"
                    value={budgetInput}
                    onChange={(event) => setBudgetInput(event.target.value)}
                    placeholder="750"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="category-budget-note">
                    Note for Jenny / agents
                  </Label>
                  <Textarea
                    id="category-budget-note"
                    value={noteInput}
                    onChange={(event) => setNoteInput(event.target.value)}
                    placeholder="Why this cap matters, exceptions, or why this category should stay disabled."
                    rows={4}
                  />
                </div>
              </div>

              <div className="flex items-center justify-between rounded-2xl border border-border/35 bg-surface-muted/15 p-4">
                <div>
                  <p className="text-sm font-semibold text-text">
                    Hide this category
                  </p>
                  <p className="mt-1 text-sm text-text-muted">
                    Disabled categories stay out of the budget table. A note is
                    required.
                  </p>
                </div>
                <Button
                  type="button"
                  variant={disabled ? 'default' : 'outline'}
                  onClick={() => setDisabled((current) => !current)}
                >
                  {disabled ? 'Hidden' : 'Visible'}
                </Button>
              </div>
            </div>
          ) : null}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setSelectedCategory(null)}
            >
              Cancel
            </Button>
            {selectedCategory?.foundMonthlyBudget != null ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  const foundBudget =
                    selectedCategory.foundMonthlyBudget ?? null
                  if (foundBudget != null) {
                    setBudgetInput(String(foundBudget))
                  }
                  void saveSelectedCategory('accepted', foundBudget)
                }}
                disabled={confirmFact.isPending}
              >
                Accept suggested cap
              </Button>
            ) : null}
            <Button
              type="button"
              onClick={() => void saveSelectedCategory('manual')}
              disabled={confirmFact.isPending}
            >
              {confirmFact.isPending ? 'Saving...' : 'Save budget'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
