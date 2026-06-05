'use client'

import { ChevronDown, ChevronRight } from 'lucide-react'
import { Fragment } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type {
  HouseholdSpendingCategory,
  HouseholdSpendingTransaction,
} from '@/lib/api/household'
import { formatCurrency, formatEnumLabel } from '@/lib/formatters'
import { cn } from '@/lib/utils'
import { budgetStatus } from './budget-helpers'
import { TransactionEditor } from './TransactionEditor'
import { type BudgetRowEntry, entryBreach } from './useBudgetRows'

export interface BudgetRowProps {
  entry: BudgetRowEntry
  isExpanded: boolean
  categoryTransactions: HouseholdSpendingTransaction[]
  confirmPending: boolean
  onToggleExpand: (category: string) => void
  onCollapse: () => void
  onConfirmFound: (
    row: HouseholdSpendingCategory,
    meta: BudgetRowEntry['meta'],
    foundBudget: number,
  ) => void
  onOpenBudget: (row: HouseholdSpendingCategory) => void
  transactionEditorProps: Omit<
    React.ComponentProps<typeof TransactionEditor>,
    'transaction'
  >
}

export function BudgetRow({
  entry,
  isExpanded,
  categoryTransactions,
  confirmPending,
  onToggleExpand,
  onCollapse,
  onConfirmFound,
  onOpenBudget,
  transactionEditorProps,
}: BudgetRowProps) {
  const { row, meta, currentBudget, foundBudget, note } = entry
  const status = budgetStatus(
    currentBudget,
    foundBudget,
    row.averageMonthlySpend,
  )
  const breach = entryBreach(entry)

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
            onClick={() => onToggleExpand(row.category)}
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
          {breach.isOver ? (
            <div className="mt-1 text-xs font-medium text-warning">
              {formatCurrency(breach.overAmount, { decimals: 0 })}
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
                onClick={() => onConfirmFound(row, meta, foundBudget)}
                disabled={confirmPending}
              >
                Accept
              </Button>
            ) : null}
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => onOpenBudget(row)}
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
                  onClick={onCollapse}
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
                  {categoryTransactions.map((transaction) => (
                    <TransactionEditor
                      key={transaction.id}
                      transaction={transaction}
                      {...transactionEditorProps}
                    />
                  ))}
                </div>
              )}
            </div>
          </td>
        </tr>
      ) : null}
    </Fragment>
  )
}
