'use client'

import { useMemo, useState } from 'react'
import {
  categoryPlaybook,
  trimRateForCategory,
} from '@/components/money/lever-helpers'
import {
  nextSortDirection,
  SortableTableHeader,
  type SortDirection,
} from '@/components/shared/SortableTableHeader'
import { Badge } from '@/components/ui/badge'
import type { HouseholdSpendingCategory } from '@/lib/api/household'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'

type CategoryPressureSortKey =
  | 'category'
  | 'type'
  | 'monthly'
  | 'share'
  | 'tx'
  | 'trim'
  | 'move'

function compareText(left: string, right: string) {
  return left.localeCompare(right, undefined, { sensitivity: 'base' })
}

function compareNumber(left: number, right: number) {
  return left - right
}

interface CategoryPressureTableProps {
  rows: HouseholdSpendingCategory[]
  isLoading: boolean
  hasData: boolean
}

export function CategoryPressureTable({
  rows,
  isLoading,
  hasData,
}: CategoryPressureTableProps) {
  const [sortKey, setSortKey] = useState<CategoryPressureSortKey | null>(null)
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  const displayRows = useMemo(() => {
    if (sortKey === null) {
      return rows
    }
    const direction = sortDirection === 'asc' ? 1 : -1
    return [...rows].sort((left, right) => {
      let result = 0
      switch (sortKey) {
        case 'category':
          result = compareText(left.category, right.category)
          break
        case 'type':
          result = compareText(left.essentiality, right.essentiality)
          break
        case 'monthly':
          result = compareNumber(
            left.averageMonthlySpend,
            right.averageMonthlySpend,
          )
          break
        case 'share':
          result = compareNumber(left.shareOfSpend, right.shareOfSpend)
          break
        case 'tx':
          result = compareNumber(left.transactionCount, right.transactionCount)
          break
        case 'trim':
          result = compareNumber(
            left.averageMonthlySpend *
              trimRateForCategory(left.category, left.essentiality),
            right.averageMonthlySpend *
              trimRateForCategory(right.category, right.essentiality),
          )
          break
        case 'move':
          result = compareText(
            categoryPlaybook(left.category, left.essentiality),
            categoryPlaybook(right.category, right.essentiality),
          )
          break
      }
      return result * direction || compareText(left.category, right.category)
    })
  }, [rows, sortDirection, sortKey])

  function defaultSortDirection(field: CategoryPressureSortKey): SortDirection {
    return field === 'category' || field === 'type' || field === 'move'
      ? 'asc'
      : 'desc'
  }

  function handleSort(field: CategoryPressureSortKey) {
    setSortDirection((current) =>
      nextSortDirection(sortKey, field, current, defaultSortDirection(field)),
    )
    setSortKey(field)
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
      <div className="max-h-[34vh] overflow-auto [scrollbar-gutter:stable_both-edges]">
        <table className="w-full min-w-[1100px] border-separate border-spacing-0 text-sm">
          <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
            <tr>
              <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                <SortableTableHeader
                  field="category"
                  label="Category"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                <SortableTableHeader
                  field="type"
                  label="Type"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                <SortableTableHeader
                  field="monthly"
                  label="Monthly"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                  align="right"
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                <SortableTableHeader
                  field="share"
                  label="Share"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                  align="right"
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                <SortableTableHeader
                  field="tx"
                  label="Tx"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                  align="right"
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                <SortableTableHeader
                  field="trim"
                  label="Modeled trim"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                  align="right"
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                <SortableTableHeader
                  field="move"
                  label="Move"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading && !hasData ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-3 py-10 text-center text-sm text-text-muted"
                >
                  Loading category levers...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  className="px-3 py-10 text-center text-sm text-text-muted"
                >
                  No category pressure in this window.
                </td>
              </tr>
            ) : (
              displayRows.map((row: HouseholdSpendingCategory) => {
                const trimRate = trimRateForCategory(
                  row.category,
                  row.essentiality,
                )
                return (
                  <tr
                    key={`${row.category}-${row.essentiality}`}
                    className="border-b border-border/30 align-top transition-colors hover:bg-surface-muted/20"
                  >
                    <td className="border-b border-border/20 px-3 py-2.5 font-medium text-text">
                      {row.category}
                    </td>
                    <td className="border-b border-border/20 px-3 py-2.5">
                      <Badge
                        variant={
                          row.essentiality === 'essential'
                            ? 'success'
                            : row.essentiality === 'discretionary'
                              ? 'warning'
                              : 'outline'
                        }
                      >
                        {formatEnumLabel(row.essentiality)}
                      </Badge>
                    </td>
                    <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                      {formatCurrency(row.averageMonthlySpend, {
                        decimals: 2,
                      })}
                    </td>
                    <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                      {formatPercent(row.shareOfSpend * 100, {
                        decimals: 0,
                      })}
                    </td>
                    <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                      {row.transactionCount}
                    </td>
                    <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                      {trimRate > 0
                        ? `${formatCurrency(
                            row.averageMonthlySpend * trimRate,
                            {
                              decimals: 0,
                            },
                          )} · ${formatPercent(trimRate * 100, { decimals: 0 })}`
                        : '—'}
                    </td>
                    <td className="border-b border-border/20 px-3 py-2.5 text-xs text-text-muted">
                      {categoryPlaybook(row.category, row.essentiality)}
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
