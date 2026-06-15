'use client'

import type * as React from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Button } from '@/components/ui/button'
import { BudgetRow } from './BudgetRow'
import type { TransactionEditor } from './TransactionEditor'
import type { BudgetRowEntry } from './useBudgetRows'

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
                Owner / note
              </th>
              <th className="border-b border-border/35 px-4 py-3 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted">
                Suggested
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
