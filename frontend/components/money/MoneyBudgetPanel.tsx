'use client'

import { useEffect, useMemo, useState } from 'react'
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
  useHouseholdDashboard,
  useHouseholdFacts,
  useHouseholdSpending,
} from '@/lib/hooks/useHousehold'
import { AffordabilityCard } from './AffordabilityCard'
import { BudgetDialog } from './BudgetDialog'
import { BudgetStatRow } from './BudgetStatRow'
import { BudgetTable } from './BudgetTable'
import { CategoryTrendChart } from './CategoryTrendChart'
import { ConnectedSpendTrendChart } from './ConnectedSpendTrendChart'
import type { InlineComboboxCommitOptions } from './InlineComboboxField'
import { MoneyInboxCard } from './MoneyInboxCard'
import { MonthComparatorRow } from './MonthComparatorRow'
import { MonthSelector } from './MonthSelector'
import { MonthVerdictLine } from './MonthVerdictLine'
import { NeedsWantsMixedCard } from './NeedsWantsMixedCard'
import { NewThisMonthCard } from './NewThisMonthCard'
import { OwnerSpendInsightsCard } from './OwnerSpendInsightsCard'
import { normalizeTrustStatus } from './overview-helpers'
import { RetirementPhaseCard } from './RetirementPhaseCard'
import {
  type BudgetRowEntry,
  TREND_TOP_N,
  useBudgetRows,
} from './useBudgetRows'
import { WhatChangedCard } from './WhatChangedCard'

export function MoneyBudgetPanel() {
  // null means "whatever month the household is living in" -- the server
  // decides that, so a stale tab cannot pin the panel to a month that has ended.
  const [month, setMonth] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] =
    useState<HouseholdSpendingCategory | null>(null)
  const [budgetInput, setBudgetInput] = useState('')
  const [noteInput, setNoteInput] = useState('')
  const [ownerInput, setOwnerInput] = useState('')
  const [disabled, setDisabled] = useState(false)
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null)
  const [isolatedSeries, setIsolatedSeries] = useState<string | null>(null)
  const {
    data: spending,
    error,
    refetch,
    isFetching,
    isLoading,
  } = useHouseholdSpending(month ? { month } : undefined)
  const { data: facts = [] } = useHouseholdFacts()
  // Already fetched by the Money page for every tab, so this is the cached
  // payload rather than a second round trip. Affordability is read from it
  // rather than recomputed here: one server figure, however many screens show it.
  const { data: dashboard, isLoading: isDashboardLoading } =
    useHouseholdDashboard()
  const confirmFact = useConfirmFact()
  const categorizeTransaction = useCategorizeHouseholdTransaction()

  const {
    budgetMeta,
    categoryOptions,
    transactionsByCategory,
    activeRows,
    hiddenRows,
    sortedActiveRows,
    foundBudgetRows,
    foundBudgetTotal,
    foundBudgetCategoryCount,
    unknownTransactions,
    unknownSpend,
    trendMeta,
    chartCategories,
    isolatedCap,
    ownerSpendRows,
  } = useBudgetRows({ spending, facts, isolatedSeries })
  // Free to spend subtracts two things the household can go fix: balances it
  // reads off accounts, and the essentials it reads off this month's spending.
  // Name whichever is behind rather than a generic "stale data" that leaves the
  // reader nowhere to go.
  const affordabilityCaveats = useMemo(() => {
    if (!dashboard) {
      return []
    }
    const caveats: string[] = []
    if (normalizeTrustStatus(dashboard.overview.netWorthStatus) !== 'current') {
      caveats.push('Cash and card balances need a refresh.')
    }
    if (
      normalizeTrustStatus(dashboard.overview.monthlySpendStatus) !== 'current'
    ) {
      caveats.push("This month's essentials are still an estimate.")
    }
    return caveats
  }, [dashboard])
  const connectedMonthStats = useMemo(() => {
    const endDate = spending?.summary.endDate
    const monthKey = endDate?.slice(0, 7)
    const monthRows =
      monthKey == null
        ? []
        : (spending?.transactions ?? []).filter(
            (transaction) =>
              transaction.date.slice(0, 7) === monthKey &&
              transaction.sourceKind === 'transaction' &&
              ['plaid', 'snaptrade'].includes(
                transaction.sourceSystem?.toLowerCase() ?? '',
              ),
          )
    const total = monthRows.reduce(
      (sum, transaction) => sum + transaction.amount,
      0,
    )
    const pendingRows = monthRows.filter((transaction) => transaction.pending)
    const pendingSpend = pendingRows.reduce(
      (sum, transaction) => sum + transaction.amount,
      0,
    )
    return {
      connectedMonthToDateSpend: Math.round(total * 100) / 100,
      pendingCount: pendingRows.length,
      pendingSpend: Math.round(pendingSpend * 100) / 100,
      evidenceSpend:
        Math.round(((spending?.summary.monthToDateSpend ?? 0) - total) * 100) /
        100,
      asOfDate: endDate ?? null,
    }
  }, [
    spending?.summary.endDate,
    spending?.summary.monthToDateSpend,
    spending?.transactions,
  ])
  const coverageMonthKeys = spending?.summary.coverageMonthKeys ?? []
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
          ownerName: entry.meta?.ownerName ?? null,
        }),
      })
    }
  }

  async function saveTransactionCategory(
    transaction: HouseholdSpendingTransaction,
    category: string,
    options?: InlineComboboxCommitOptions,
  ) {
    const trimmed = category.trim()
    if (!trimmed) {
      return
    }
    await categorizeTransaction.mutateAsync({
      transactionId: transaction.id,
      category: trimmed,
      essentiality: transaction.essentiality || 'mixed',
      applyToMerchant: options?.applyRule === true,
    })
  }

  const transactionEditorProps = {
    categoryOptions,
    categorizePending: categorizeTransaction.isPending,
    onCommitCategory: (
      transaction: HouseholdSpendingTransaction,
      category: string,
      options?: InlineComboboxCommitOptions,
    ) => void saveTransactionCategory(transaction, category, options),
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
        ownerName: meta?.ownerName ?? null,
      }),
    })
  }

  useEffect(() => {
    if (!selectedCategory) {
      setBudgetInput('')
      setNoteInput('')
      setOwnerInput('')
      setDisabled(false)
      return
    }
    const meta = budgetMeta.get(selectedCategory.category)
    setBudgetInput(
      meta?.monthlyTarget != null ? String(meta.monthlyTarget) : '',
    )
    setNoteInput(meta?.note ?? '')
    setOwnerInput(meta?.ownerName ?? '')
    setDisabled(meta?.disabled === true)
  }, [budgetMeta, selectedCategory])

  useEffect(() => {
    if (
      expandedCategory &&
      !activeRows.some((entry) => entry.row.category === expandedCategory)
    ) {
      setExpandedCategory(null)
    }
  }, [activeRows, expandedCategory])

  function saveCategoryBudget(
    row: HouseholdSpendingCategory,
    meta: BudgetRowEntry['meta'],
    changes: { monthlyTarget?: number | null; ownerName?: string | null },
  ) {
    const monthlyTarget =
      changes.monthlyTarget !== undefined
        ? changes.monthlyTarget
        : (row.confirmedMonthlyBudget ?? meta?.monthlyTarget ?? null)
    void confirmFact.mutateAsync({
      factKey: `${CATEGORY_BUDGET_PREFIX}${row.category}`,
      factValue: serializeCategoryBudgetMeta({
        category: row.category,
        note: meta?.note ?? row.budgetNote ?? '',
        disabled: row.budgetDisabled ?? meta?.disabled === true,
        monthlyTarget,
        source: 'manual',
        ownerName:
          changes.ownerName !== undefined
            ? changes.ownerName
            : (meta?.ownerName ?? null),
      }),
    })
  }

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
        ownerName: ownerInput.trim() || null,
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
          <MonthSelector
            availableMonths={spending?.availableMonths ?? []}
            month={month ?? spending?.summary.month ?? null}
            onChange={setMonth}
            isMonthToDate={spending?.summary.isMonthToDate ?? false}
            basisLabel={spending?.summary.basisLabel}
            disabled={isLoading}
          />
        }
      >
        <div className="mb-3 grid items-start gap-3 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <MonthVerdictLine
            verdict={spending?.budgetVerdict}
            isLoading={isLoading}
          />
          <AffordabilityCard
            affordability={dashboard?.budgetSnapshot.affordability}
            isLoading={isDashboardLoading}
            caveats={affordabilityCaveats}
          />
        </div>
        <MonthComparatorRow
          monthLabel={spending?.summary.monthLabel ?? '—'}
          totalSpend={spending?.summary.totalSpend}
          totalIncome={spending?.summary.totalIncome}
          netCashFlow={spending?.summary.netCashFlow}
          oneTimeSpend={spending?.summary.oneTimeSpend}
          everydaySpend={spending?.summary.everydaySpend}
          comparators={spending?.comparators ?? []}
          coverageMonthKeys={coverageMonthKeys}
        />
        <div className="mt-3">
          <BudgetStatRow
            unknownTransactionCount={unknownTransactions.length}
            unknownSpend={unknownSpend}
            foundBudgetTotal={foundBudgetTotal}
            foundBudgetCategoryCount={foundBudgetCategoryCount}
            connectedMonthToDateSpend={
              connectedMonthStats.connectedMonthToDateSpend
            }
            monthToDateSpend={spending?.summary.monthToDateSpend}
            connectedPendingCount={connectedMonthStats.pendingCount}
            connectedPendingSpend={connectedMonthStats.pendingSpend}
            evidenceMonthToDateSpend={connectedMonthStats.evidenceSpend}
            monthToDateAsOfDate={connectedMonthStats.asOfDate}
          />
        </div>
      </SectionCard>

      <MoneyInboxCard inbox={dashboard?.inbox} isLoading={isDashboardLoading} />

      <div className="grid gap-3 lg:grid-cols-2">
        <NeedsWantsMixedCard
          dashboard={dashboard}
          isLoading={isDashboardLoading}
        />
        <RetirementPhaseCard
          block={dashboard?.retirementContributionTracker}
          isLoading={isDashboardLoading}
        />
      </div>

      <WhatChangedCard variance={spending?.spendVariance} />

      <NewThisMonthCard
        clusters={spending?.newThisMonth}
        monthLabel={spending?.summary.monthLabel ?? 'this month'}
      />

      <ConnectedSpendTrendChart
        transactions={spending?.transactions ?? []}
        isLoading={isLoading}
      />

      <CategoryTrendChart
        timeframeLabel={spending?.summary.monthLabel}
        trendData={trendMeta.data}
        trendCategories={trendMeta.categories}
        chartCategories={chartCategories}
        isolatedSeries={isolatedSeries}
        setIsolatedSeries={setIsolatedSeries}
        isolatedCap={isolatedCap}
        trendTopN={TREND_TOP_N}
      />

      <OwnerSpendInsightsCard
        timeframeLabel={spending?.summary.monthLabel}
        ownerSpendRows={ownerSpendRows}
      />

      <BudgetTable
        isLoading={isLoading}
        hasData={spending != null}
        activeRowCount={activeRows.length}
        sortedActiveRows={sortedActiveRows}
        foundBudgetRowCount={foundBudgetRows.length}
        verdict={spending?.budgetVerdict}
        hiddenCount={hiddenRows.length}
        confirmPending={confirmFact.isPending}
        expandedCategory={expandedCategory}
        categoryTransactionsFor={(category) =>
          transactionsByCategory.get(category) ?? []
        }
        onAcceptAll={() => void acceptAllSuggestedCaps()}
        setExpandedCategory={setExpandedCategory}
        onConfirmFound={confirmFoundCap}
        onSaveBudget={saveCategoryBudget}
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
        ownerInput={ownerInput}
        setOwnerInput={setOwnerInput}
        disabled={disabled}
        setDisabled={setDisabled}
        confirmPending={confirmFact.isPending}
        onSaveManual={() => void saveSelectedCategory('manual')}
        onAcceptSuggested={acceptSuggestedFromDialog}
      />
    </div>
  )
}
