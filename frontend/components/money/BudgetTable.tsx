'use client'

import type * as React from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import type { HouseholdSpendingCategory } from '@/lib/api/household'
import { BudgetRow } from './BudgetRow'
import type { TransactionEditor } from './TransactionEditor'
import type { BudgetRowEntry } from './useBudgetRows'

export interface BudgetTableProps {
  isLoading: boolean
  hasData: boolean
  activeRowCount: number
  sortedActiveRows: BudgetRowEntry[]
  foundBudgetRowCount: number
  confirmPending: boolean
  expandedCategory: string | null
  categoryTransactionsFor: (
    category: string,
  ) => React.ComponentProps<typeof BudgetRow>['categoryTransactions']
  onAcceptAll: () => void
  setExpandedCategory: Dispatch<SetStateAction<string | null>>
  onConfirmFound: React.ComponentProps<typeof BudgetRow>['onConfirmFound']
  onOpenBudget: (row: HouseholdSpendingCategory) => void
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
  confirmPending,
  expandedCategory,
  categoryTransactionsFor,
  onAcceptAll,
  setExpandedCategory,
  onConfirmFound,
  onOpenBudget,
  transactionEditorProps,
}: BudgetTableProps) {
  return (
    <SectionCard
      variant="surface"
      title="Category budgets"
      description="Expand a category to inspect the purchases behind it, correct wrong categories, or create merchant rules."
      padding="none"
      className="overflow-hidden"
      actions={
        foundBudgetRowCount > 0 ? (
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
              sortedActiveRows.map((entry) => (
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
                  onOpenBudget={onOpenBudget}
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
