'use client'

import Link from 'next/link'
import {
  type SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  CATEGORY_BUDGET_PREFIX,
  serializeCategoryBudgetMeta,
} from '@/components/money/household-fact-metadata'
import { LoadErrorState } from '@/components/shared/LoadErrorState'
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
import { useUsableContentTiming } from '@/lib/hooks/useUsableContentTiming'
import { AffordabilityCard } from './AffordabilityCard'
import { BudgetDialog } from './BudgetDialog'
import { BudgetStatRow } from './BudgetStatRow'
import { BudgetTable } from './BudgetTable'
import { CapPlanCard } from './CapPlanCard'
import { CardCommitmentsCard } from './CardCommitmentsCard'
import { CategoryTrendChart } from './CategoryTrendChart'
import { ConnectedSpendTrendChart } from './ConnectedSpendTrendChart'
import { IncomeAnchorCard } from './IncomeAnchorCard'
import type { InlineComboboxCommitOptions } from './InlineComboboxField'
import { MoneyInboxCard } from './MoneyInboxCard'
import { MonthComparatorRow } from './MonthComparatorRow'
import { MonthlyReviewAgreement } from './MonthlyReviewAgreement'
import { MonthSelector } from './MonthSelector'
import { MonthVerdictLine } from './MonthVerdictLine'
import { NeedsWantsMixedCard } from './NeedsWantsMixedCard'
import { NewThisMonthCard } from './NewThisMonthCard'
import { OwnerSpendInsightsCard } from './OwnerSpendInsightsCard'
import { normalizeTrustStatus } from './overview-helpers'
import { PushAlertsCard } from './PushAlertsCard'
import { RetirementPhaseCard } from './RetirementPhaseCard'
import { ReviewPurchaseActions } from './ReviewPurchaseActions'
import { SavingsPlanCard } from './SavingsPlanCard'
import { SinkingFundsCard } from './SinkingFundsCard'
import {
  type BudgetRowEntry,
  TREND_TOP_N,
  useBudgetRows,
} from './useBudgetRows'
import { reviewLedgerHref, useMoneyQuery } from './useMoneyQuery'
import { WhatChangedCard } from './WhatChangedCard'

export function MoneyBudgetPanel() {
  // null means "whatever month the household is living in" -- the server
  // decides that, so a stale tab cannot pin the panel to a month that has ended.
  const [month, setMonthQuery] = useMoneyQuery('month', '')
  const setMonth = (value: string | null) => setMonthQuery(value ?? '')
  const [selectedCategory, setSelectedCategory] =
    useState<HouseholdSpendingCategory | null>(null)
  const [budgetInput, setBudgetInput] = useState('')
  const [noteInput, setNoteInput] = useState('')
  const [ownerInput, setOwnerInput] = useState('')
  const [disabled, setDisabled] = useState(false)
  const [expandedCategoryQuery, setExpandedCategoryQuery] = useMoneyQuery(
    'reviewCategory',
    '',
  )
  const expandedCategory = expandedCategoryQuery || null
  const setExpandedCategory = useCallback(
    (value: SetStateAction<string | null>) =>
      setExpandedCategoryQuery(
        (typeof value === 'function' ? value(expandedCategory) : value) ?? '',
      ),
    [expandedCategory, setExpandedCategoryQuery],
  )
  const [isolatedSeries, setIsolatedSeries] = useState<string | null>(null)
  const {
    data: spending,
    error,
    refetch,
    isFetching,
    isLoading,
  } = useHouseholdSpending(month ? { month } : undefined)
  useUsableContentTiming(
    'money-review',
    Boolean(spending?.summary) && !error,
    month ?? '',
  )
  const { data: facts = [] } = useHouseholdFacts()
  const [setupOpen, setSetupOpen] = useState(false)
  const {
    data: dashboard,
    isLoading: isDashboardLoading,
    error: dashboardError,
    refetch: refetchDashboard,
  } = useHouseholdDashboard({ enabled: setupOpen })
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
      spending &&
      expandedCategory &&
      !activeRows.some((entry) => entry.row.category === expandedCategory)
    ) {
      setExpandedCategory(null)
    }
  }, [activeRows, expandedCategory, spending, setExpandedCategory])

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
        title="Monthly review"
        actions={
          <MonthSelector
            availableMonths={spending?.availableMonths ?? []}
            month={month || spending?.summary.month || null}
            onChange={setMonth}
            isMonthToDate={spending?.summary.isMonthToDate ?? false}
            basisLabel={spending?.summary.basisLabel}
            disabled={isLoading}
          />
        }
      >
        {spending ? (
          <p className="mb-3 text-xs text-text-muted">
            {spending.summary.basisLabel} ·{' '}
            {spending.summary.coverageStatus === 'current'
              ? 'Recorded activity; spending feeds current'
              : 'Recorded activity; spending coverage needs review'}
          </p>
        ) : null}
        {spending ? (
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
        ) : null}
        <div className="mt-3">
          <MonthVerdictLine
            verdict={spending?.budgetVerdict}
            isLoading={isLoading}
          />
        </div>
        <p className="mt-3 text-xs text-text-muted">
          {spending?.summary.coverageDetail}
        </p>
        {spending ? (
          <details className="mt-3">
            <summary className="mb-2 cursor-pointer text-sm text-text-muted">
              Evidence and cap setup
            </summary>
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
          </details>
        ) : (
          <p className="text-sm text-text-muted">
            Loading this month’s transactions…
          </p>
        )}
        {spending ? (
          <Link
            href={reviewLedgerHref(spending.summary.month)}
            className="mt-3 inline-block text-sm text-primary underline"
          >
            Check {spending.summary.monthLabel} in the ledger
          </Link>
        ) : null}
      </SectionCard>

      <WhatChangedCard variance={spending?.spendVariance} />

      <NewThisMonthCard
        clusters={spending?.newThisMonth}
        monthLabel={spending?.summary.monthLabel ?? 'this month'}
      />

      {spending?.reviewPlan ? (
        <MonthlyReviewAgreement
          key={spending.summary.month}
          plan={spending.reviewPlan}
        />
      ) : null}

      <ReviewPurchaseActions />

      <BudgetTable
        month={spending?.summary.month}
        isProvisional={
          spending?.summary.isMonthToDate ||
          spending?.summary.coverageStatus !== 'current'
        }
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

      <details
        open={setupOpen}
        onToggle={(event) => setSetupOpen(event.currentTarget.open)}
        className="rounded-2xl border border-border/35 p-4"
      >
        <summary className="cursor-pointer font-medium">
          Funding, caps, and household setup
        </summary>
        {setupOpen && (
          <div className="mt-4 space-y-4">
            {dashboardError && !dashboard ? (
              <LoadErrorState
                title="Current household setup could not be loaded."
                onRetry={() => void refetchDashboard()}
              />
            ) : (
              <>
                <div>
                  <p className="mb-2 text-xs text-text-muted">
                    Current cash position · updated{' '}
                    {dashboard
                      ? new Date(dashboard.generatedAt).toLocaleDateString()
                      : 'loading…'}
                  </p>
                  <AffordabilityCard
                    affordability={dashboard?.budgetSnapshot.affordability}
                    isLoading={isDashboardLoading}
                    caveats={affordabilityCaveats}
                  />
                </div>
                <div className="grid items-start gap-3 lg:grid-cols-2">
                  {/* What a normal month brings in sits on the review screen because
            every cap Phase 3 sets is priced off it, and because the saved
            take-home target it replaces is above what actually arrives. */}
                  <IncomeAnchorCard
                    anchor={dashboard?.incomeAnchor}
                    isLoading={isDashboardLoading}
                  />
                  <SavingsPlanCard
                    plan={dashboard?.savingsPlan}
                    isLoading={isDashboardLoading}
                  />
                </div>

                {/* The caps are priced off the anchor, not off history: a plan whose
          caps sum above take-home lets "under budget" and "going broke" be
          true at once (D6). */}
                <CapPlanCard plan={spending?.capPlan} isLoading={isLoading} />

                {/* Priced off the same anchor above: what the lumpy costs need each
          month, before any category cap divides up what is left. */}
                <SinkingFundsCard
                  funds={dashboard?.sinkingFunds}
                  isLoading={isDashboardLoading}
                />

                {/* The fees subtracted one card up, itemised — plus the balances and any
          bonus deadline, which lived only on the Cards tab until now (P0-20). */}
                <CardCommitmentsCard
                  commitments={dashboard?.cardCommitments}
                  isLoading={isDashboardLoading}
                />

                <MoneyInboxCard
                  inbox={dashboard?.inbox}
                  isLoading={isDashboardLoading}
                />

                {/* The same findings the inbox above collects, on the phone — the inbox
          only reaches someone already looking at this screen (D11). */}
                <PushAlertsCard />

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
              </>
            )}
          </div>
        )}
      </details>
      <details className="rounded-2xl border border-border/35 p-4">
        <summary className="cursor-pointer font-medium">
          Spending trends and owners
        </summary>
        <div className="mt-4 space-y-4">
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
        </div>
      </details>

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
