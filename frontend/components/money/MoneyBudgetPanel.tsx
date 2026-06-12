'use client'

import { useEffect, useState } from 'react'
import {
  CATEGORY_BUDGET_PREFIX,
  serializeCategoryBudgetMeta,
} from '@/components/money/household-fact-metadata'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import type {
  HouseholdSpendingCategory,
  HouseholdSpendingTransaction,
} from '@/lib/api/household'
import {
  useCategorizeHouseholdTransaction,
  useConfirmFact,
  useHouseholdFacts,
  useHouseholdSpending,
} from '@/lib/hooks/useHousehold'
import { BudgetDialog } from './BudgetDialog'
import { BudgetStatRow } from './BudgetStatRow'
import { BudgetTable } from './BudgetTable'
import { type BudgetWindow, budgetWindows } from './budget-helpers'
import { CategoryTrendChart } from './CategoryTrendChart'
import {
  type RecategorizeDraft,
  startRecategorizeDraft,
} from './category-options'
import {
  type BudgetRowEntry,
  TREND_TOP_N,
  useBudgetRows,
} from './useBudgetRows'

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

  const {
    budgetMeta,
    categoryOptions,
    transactionsByCategory,
    merchantAggregates,
    activeRows,
    hiddenRows,
    sortedActiveRows,
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
  } = useBudgetRows({ spending, facts, isolatedSeries })

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
    setRecategorizeDraft(startRecategorizeDraft(transaction))
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

  const transactionEditorProps = {
    recategorizeDraft,
    setRecategorizeDraft,
    categoryPickerOpenFor,
    setCategoryPickerOpenFor,
    categoryOptions,
    merchantAggregates,
    categorizePending: categorizeTransaction.isPending,
    onStartRecategorize: startRecategorize,
    onSaveRecategorize: (transaction: HouseholdSpendingTransaction) =>
      void saveRecategorize(transaction),
  }

  function confirmFoundCap(
    row: HouseholdSpendingCategory,
    meta: BudgetRowEntry['meta'],
    foundBudget: number,
  ) {
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

  function acceptSuggestedFromDialog() {
    if (!selectedCategory) {
      return
    }
    const foundBudget = selectedCategory.foundMonthlyBudget ?? null
    if (foundBudget != null) {
      setBudgetInput(String(foundBudget))
    }
    void saveSelectedCategory('accepted', foundBudget)
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
        <BudgetStatRow
          averageMonthlySpend={spending?.summary.averageMonthlySpend}
          foundBudgetTotal={foundBudgetTotal}
          foundBudgetCategoryCount={foundBudgetCategoryCount}
          confirmedBudgetTotal={confirmedBudgetTotal}
          unknownTransactionCount={unknownTransactions.length}
          unknownSpend={unknownSpend}
          budgetedCategoryCount={budgetedCategoryCount}
          confirmedBudgetCategoryCount={confirmedBudgetCategoryCount}
          overBudgetCount={overBudgetCount}
          foundOverBudgetCount={foundOverBudgetCount}
          confirmedOverBudgetCount={confirmedOverBudgetCount}
          averageMonthlyIncome={spending?.summary.averageMonthlyIncome}
          netCashFlow={spending?.summary.netCashFlow}
          savingsRate={spending?.summary.savingsRate}
          monthToDateSpend={spending?.summary.monthToDateSpend}
          windowLabel={
            budgetWindows.find((option) => option.value === window)?.label ??
            window
          }
        />
      </SectionCard>

      <CategoryTrendChart
        timeframeLabel={spending?.summary.timeframeLabel}
        trendData={trendMeta.data}
        trendCategories={trendMeta.categories}
        chartCategories={chartCategories}
        isolatedSeries={isolatedSeries}
        setIsolatedSeries={setIsolatedSeries}
        isolatedCap={isolatedCap}
        trendTopN={TREND_TOP_N}
      />

      <BudgetTable
        isLoading={isLoading}
        hasData={spending != null}
        activeRowCount={activeRows.length}
        sortedActiveRows={sortedActiveRows}
        foundBudgetRowCount={foundBudgetRows.length}
        hiddenCount={hiddenRows.length}
        confirmPending={confirmFact.isPending}
        expandedCategory={expandedCategory}
        categoryTransactionsFor={(category) =>
          transactionsByCategory.get(category) ?? []
        }
        onAcceptAll={() => void acceptAllSuggestedCaps()}
        setExpandedCategory={setExpandedCategory}
        onConfirmFound={confirmFoundCap}
        onOpenBudget={setSelectedCategory}
        transactionEditorProps={transactionEditorProps}
      />

      {hiddenRows.length > 0 ? (
        // SectionCard does not forward an id, so the anchor target wraps it.
        <div id="hidden-categories" className="scroll-mt-6">
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
        </div>
      ) : null}

      <BudgetDialog
        selectedCategory={selectedCategory}
        onClose={() => setSelectedCategory(null)}
        budgetInput={budgetInput}
        setBudgetInput={setBudgetInput}
        noteInput={noteInput}
        setNoteInput={setNoteInput}
        disabled={disabled}
        setDisabled={setDisabled}
        confirmPending={confirmFact.isPending}
        onSaveManual={() => void saveSelectedCategory('manual')}
        onAcceptSuggested={acceptSuggestedFromDialog}
      />
    </div>
  )
}
