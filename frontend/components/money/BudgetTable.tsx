'use client'

import type * as React from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { useMemo, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { BudgetRow } from './BudgetRow'
import {
  nextSortDirection,
  SortableTableHeader,
  type SortDirection,
} from './SortableTableHeader'
import type { TransactionEditor } from './TransactionEditor'
import { type BudgetRowEntry, entryBreach } from './useBudgetRows'

type BudgetSortKey =
  | 'category'
  | 'type'
  | 'observed'
  | 'budget'
  | 'status'
  | 'owner'
  | 'suggested'

function compareText(left: string, right: string) {
  return left.localeCompare(right, undefined, { sensitivity: 'base' })
}

function compareNumber(left: number | null, right: number | null) {
  if (left == null && right == null) return 0
  if (left == null) return -1
  if (right == null) return 1
  return left - right
}

function statusScore(entry: BudgetRowEntry) {
  const breach = entryBreach(entry)
  if (breach.isOver) {
    return 3 + breach.overAmount
  }
  if (entry.currentBudget != null) {
    return 2
  }
  if (entry.foundBudget != null) {
    return 1
  }
  return 0
}

export interface BudgetTableProps {
  isLoading: boolean
  hasData: boolean
  activeRowCount: number
  sortedActiveRows: BudgetRowEntry[]
  foundBudgetRowCount: number
  /** Disabled categories live in the "Hidden categories" card below the table. */
  hiddenCount: number
  confirmPending: boolean
  expandedCategory: string | null
  categoryTransactionsFor: (
    category: string,
  ) => React.ComponentProps<typeof BudgetRow>['categoryTransactions']
  onAcceptAll: () => void
  setExpandedCategory: Dispatch<SetStateAction<string | null>>
  onConfirmFound: React.ComponentProps<typeof BudgetRow>['onConfirmFound']
  onSaveBudget: React.ComponentProps<typeof BudgetRow>['onSaveBudget']
  transactionEditorProps: Omit<
    React.ComponentProps<typeof TransactionEditor>,
    'transaction'
  >
}

export function BudgetTable({
  isLoading,
  hasData,
  activeRowCount,
  sortedActiveRows,
  foundBudgetRowCount,
  hiddenCount,
  confirmPending,
  expandedCategory,
  categoryTransactionsFor,
  onAcceptAll,
  setExpandedCategory,
  onConfirmFound,
  onSaveBudget,
  transactionEditorProps,
}: BudgetTableProps) {
  const [sortKey, setSortKey] = useState<BudgetSortKey | null>(null)
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  const displayRows = useMemo(() => {
    if (sortKey === null) {
      return sortedActiveRows
    }
    const direction = sortDirection === 'asc' ? 1 : -1
    return [...sortedActiveRows].sort((left, right) => {
      let result = 0
      switch (sortKey) {
        case 'category':
          result = compareText(left.row.category, right.row.category)
          break
        case 'type':
          result = compareText(left.row.essentiality, right.row.essentiality)
          break
        case 'observed':
          result = compareNumber(
            left.row.averageMonthlySpend,
            right.row.averageMonthlySpend,
          )
          break
        case 'budget':
          result = compareNumber(left.currentBudget, right.currentBudget)
          break
        case 'status':
          result = compareNumber(statusScore(left), statusScore(right))
          break
        case 'owner':
          result = compareText(
            left.meta?.ownerName ?? '',
            right.meta?.ownerName ?? '',
          )
          break
        case 'suggested':
          result = compareNumber(left.foundBudget, right.foundBudget)
          break
      }
      return (
        result * direction || compareText(left.row.category, right.row.category)
      )
    })
  }, [sortDirection, sortKey, sortedActiveRows])

  function defaultSortDirection(field: BudgetSortKey): SortDirection {
    return field === 'category' || field === 'type' || field === 'owner'
      ? 'asc'
      : 'desc'
  }

  function handleSort(field: BudgetSortKey) {
    setSortDirection((current) =>
      nextSortDirection(sortKey, field, current, defaultSortDirection(field)),
    )
    setSortKey(field)
  }

  return (
    <SectionCard
      variant="surface"
      title="Category budgets"
      description="Adjust category caps, owners, and row categories inline."
      padding="none"
      className="overflow-hidden"
      actions={
        hiddenCount > 0 || foundBudgetRowCount > 0 ? (
          <>
            {hiddenCount > 0 ? (
              <a
                href="#hidden-categories"
                className="self-center text-xs text-text-muted transition-colors hover:text-text"
              >
                {hiddenCount} hidden
              </a>
            ) : null}
            {foundBudgetRowCount > 0 ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={onAcceptAll}
                disabled={confirmPending}
              >
                Accept all {foundBudgetRowCount} suggested cap
                {foundBudgetRowCount === 1 ? '' : 's'}
              </Button>
            ) : null}
          </>
        ) : null
      }
    >
      <div className="overflow-auto">
        <table className="w-full min-w-[880px] border-separate border-spacing-0 text-sm">
          <thead className="bg-bg/95 backdrop-blur">
            <tr>
              <th className="border-b border-border/35 px-4 py-3 text-left align-middle">
                <SortableTableHeader
                  field="category"
                  label="Category"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
              </th>
              <th className="border-b border-border/35 px-4 py-3 text-left align-middle">
                <SortableTableHeader
                  field="type"
                  label="Type"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
              </th>
              <th className="border-b border-border/35 px-4 py-3 text-right align-middle">
                <SortableTableHeader
                  field="observed"
                  label="Observed / mo"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                  align="right"
                />
              </th>
              <th className="border-b border-border/35 px-4 py-3 text-right align-middle">
                <SortableTableHeader
                  field="budget"
                  label="Budget"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                  align="right"
                />
              </th>
              <th className="border-b border-border/35 px-4 py-3 text-left align-middle">
                <SortableTableHeader
                  field="status"
                  label="Status"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
              </th>
              <th className="border-b border-border/35 px-4 py-3 text-left align-middle">
                <SortableTableHeader
                  field="owner"
                  label="Owner / note"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
              </th>
              <th className="border-b border-border/35 px-4 py-3 text-right align-middle">
                <SortableTableHeader
                  field="suggested"
                  label="Suggested"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                  align="right"
                />
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading && !hasData ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-10 text-center text-sm text-text-muted"
                >
                  Loading category budgets...
                </td>
              </tr>
            ) : activeRowCount === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-4 py-10 text-center text-sm text-text-muted"
                >
                  No budgetable categories are visible yet.
                </td>
              </tr>
            ) : (
              displayRows.map((entry) => (
                <BudgetRow
                  key={entry.row.category}
                  entry={entry}
                  isExpanded={expandedCategory === entry.row.category}
                  categoryTransactions={categoryTransactionsFor(
                    entry.row.category,
                  )}
                  confirmPending={confirmPending}
                  onToggleExpand={(category) =>
                    setExpandedCategory((current) =>
                      current === category ? null : category,
                    )
                  }
                  onCollapse={() => setExpandedCategory(null)}
                  onConfirmFound={onConfirmFound}
                  onSaveBudget={onSaveBudget}
                  transactionEditorProps={transactionEditorProps}
                />
              ))
            )}
          </tbody>
        </table>
      </div>
    </SectionCard>
  )
}
