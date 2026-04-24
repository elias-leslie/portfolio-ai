'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  CATEGORY_BUDGET_PREFIX,
  categoryBudgetMetaMap,
  serializeCategoryBudgetMeta,
} from '@/components/money/household-fact-metadata'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
import { Textarea } from '@/components/ui/textarea'
import type { HouseholdSpendingCategory } from '@/lib/api/household'
import {
  formatCurrency,
  formatCurrencyWhole,
  formatEnumLabel,
} from '@/lib/formatters'
import {
  useConfirmFact,
  useHouseholdFacts,
  useHouseholdSpending,
} from '@/lib/hooks/useHousehold'

type BudgetWindow = '1m' | '3m' | '6m'

const budgetWindows: Array<{ value: BudgetWindow; label: string }> = [
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '6m', label: '6M' },
]

function roundBudget(value: number | null): number | null {
  if (value == null || !Number.isFinite(value)) {
    return null
  }
  return Math.round(value / 25) * 25
}

function recommendedBudget(
  row: HouseholdSpendingCategory,
  coverageMonths: number,
) {
  if (coverageMonths < 2 || row.averageMonthlySpend <= 0) {
    return null
  }
  if (row.essentiality === 'essential') {
    return roundBudget(row.averageMonthlySpend * 1.02)
  }
  if (row.essentiality === 'mixed') {
    return roundBudget(row.averageMonthlySpend * 0.95)
  }
  return roundBudget(row.averageMonthlySpend * 0.85)
}

function budgetStatus(
  currentBudget: number | null,
  foundBudget: number | null,
  actual: number,
) {
  if (currentBudget != null) {
    return {
      label: actual > currentBudget ? 'Over budget' : 'Budget set',
      variant:
        actual > currentBudget ? ('warning' as const) : ('success' as const),
    }
  }
  if (foundBudget != null) {
    return {
      label: actual > foundBudget ? 'Found over budget' : 'Found budget',
      variant:
        actual > foundBudget ? ('warning' as const) : ('outline' as const),
    }
  }
  return {
    label: 'Needs budget',
    variant: 'secondary' as const,
  }
}

export function MoneyBudgetPanel() {
  const [window, setWindow] = useState<BudgetWindow>('3m')
  const [selectedCategory, setSelectedCategory] =
    useState<HouseholdSpendingCategory | null>(null)
  const [budgetInput, setBudgetInput] = useState('')
  const [noteInput, setNoteInput] = useState('')
  const [disabled, setDisabled] = useState(false)
  const {
    data: spending,
    error,
    refetch,
    isFetching,
    isLoading,
  } = useHouseholdSpending({ window })
  const { data: facts = [] } = useHouseholdFacts()
  const confirmFact = useConfirmFact()

  const budgetMeta = useMemo(() => categoryBudgetMetaMap(facts), [facts])
  const coverageMonths = spending?.summary.coverageMonths ?? 0

  const rows = useMemo(() => {
    return (spending?.categories ?? [])
      .map((row) => {
        const meta = budgetMeta.get(row.category)
        const foundBudget =
          row.foundMonthlyBudget ?? recommendedBudget(row, coverageMonths)
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

  const activeRows = rows.filter((entry) => entry.disabled !== true)
  const hiddenRows = rows.filter((entry) => entry.disabled === true)
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

  function renderBudgetRow({
    row,
    meta,
    currentBudget,
    foundBudget,
    note,
  }: (typeof activeRows)[number]) {
    const status = budgetStatus(
      currentBudget,
      foundBudget,
      row.averageMonthlySpend,
    )

    return (
      <tr key={row.category} className="hover:bg-surface-muted/10">
        <td className="border-b border-border/20 px-4 py-3 font-medium text-text">
          {row.category}
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
          {currentBudget != null
            ? formatCurrency(currentBudget, { decimals: 0 })
            : foundBudget != null
              ? formatCurrency(foundBudget, { decimals: 0 })
              : '—'}
        </td>
        <td className="border-b border-border/20 px-4 py-3">
          <Badge variant={status.variant}>{status.label}</Badge>
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
        description="Set category caps where they matter. Found values stay yellow until you accept them or replace them yourself."
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
        <div className="grid gap-3 lg:grid-cols-5">
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
              Found budget total
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {formatCurrencyWhole(foundBudgetTotal)}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {foundBudgetCategoryCount} found row
              {foundBudgetCategoryCount === 1 ? '' : 's'} not accepted yet.
            </p>
          </div>
          <div className="rounded-2xl border border-border/35 bg-surface-muted/20 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
              Confirmed budget total
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
              Budgeted categories
            </p>
            <p className="mt-3 text-2xl font-semibold text-text">
              {budgetedCategoryCount}
            </p>
            <p className="mt-1 text-xs text-text-muted">
              {foundBudgetCategoryCount} found · {confirmedBudgetCategoryCount}{' '}
              confirmed.
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
              {foundOverBudgetCount} found · {confirmedOverBudgetCount}{' '}
              confirmed.
            </p>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        variant="surface"
        title="Category budgets"
        description="Only categories with useful spend history stay in view. Hidden categories can be restored below."
        padding="none"
        className="overflow-hidden"
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
                activeRows.map(renderBudgetRow)
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
              Save a manual cap, accept a found value, add context for Jenny, or
              hide the category when it should stay out of the budget view.
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
                    Found value
                  </p>
                  <p className="mt-3 text-xl font-semibold text-text">
                    {formatCurrency(
                      recommendedBudget(selectedCategory, coverageMonths),
                      { decimals: 0 },
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
            {selectedCategory &&
            recommendedBudget(selectedCategory, coverageMonths) != null ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  const foundBudget = recommendedBudget(
                    selectedCategory,
                    coverageMonths,
                  )
                  if (foundBudget != null) {
                    setBudgetInput(String(foundBudget))
                  }
                  void saveSelectedCategory('accepted', foundBudget)
                }}
                disabled={confirmFact.isPending}
              >
                Accept found value
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
