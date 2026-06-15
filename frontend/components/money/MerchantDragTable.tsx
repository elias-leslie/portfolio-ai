'use client'

import { useMemo, useState } from 'react'
import { merchantPlaybook } from '@/components/money/lever-helpers'
import type { MerchantAggregate } from '@/components/money/merchant-aggregation'
import { Badge } from '@/components/ui/badge'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'
import {
  nextSortDirection,
  SortableTableHeader,
  type SortDirection,
} from './SortableTableHeader'

type MerchantDragSortKey =
  | 'merchant'
  | 'category'
  | 'type'
  | 'total'
  | 'share'
  | 'avg'
  | 'tx'
  | 'move'

function compareText(left: string, right: string) {
  return left.localeCompare(right, undefined, { sensitivity: 'base' })
}

function compareNumber(left: number, right: number) {
  return left - right
}

interface MerchantDragTableProps {
  rows: MerchantAggregate[]
  totalSpend: number
  isLoading: boolean
  hasData: boolean
}

export function MerchantDragTable({
  rows,
  totalSpend,
  isLoading,
  hasData,
}: MerchantDragTableProps) {
  const [sortKey, setSortKey] = useState<MerchantDragSortKey | null>(null)
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  const displayRows = useMemo(() => {
    const sourceRows = sortKey === null ? rows : [...rows]
    if (sortKey === null) {
      return sourceRows.slice(0, 50)
    }
    const direction = sortDirection === 'asc' ? 1 : -1
    sourceRows.sort((left, right) => {
      let result = 0
      switch (sortKey) {
        case 'merchant':
          result = compareText(left.merchant, right.merchant)
          break
        case 'category':
          result = compareText(left.category, right.category)
          break
        case 'type':
          result = compareText(left.essentiality, right.essentiality)
          break
        case 'total':
        case 'share':
          result = compareNumber(left.totalSpend, right.totalSpend)
          break
        case 'avg':
          result = compareNumber(
            left.totalSpend / left.transactionCount,
            right.totalSpend / right.transactionCount,
          )
          break
        case 'tx':
          result = compareNumber(left.transactionCount, right.transactionCount)
          break
        case 'move':
          result = compareText(
            merchantPlaybook(
              left.category,
              left.essentiality,
              left.transactionCount,
            ),
            merchantPlaybook(
              right.category,
              right.essentiality,
              right.transactionCount,
            ),
          )
          break
      }
      return result * direction || compareText(left.merchant, right.merchant)
    })
    return sourceRows.slice(0, 50)
  }, [rows, sortDirection, sortKey])

  function defaultSortDirection(field: MerchantDragSortKey): SortDirection {
    return ['merchant', 'category', 'type', 'move'].includes(field)
      ? 'asc'
      : 'desc'
  }

  function handleSort(field: MerchantDragSortKey) {
    setSortDirection((current) =>
      nextSortDirection(sortKey, field, current, defaultSortDirection(field)),
    )
    setSortKey(field)
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
      <div className="max-h-[40vh] overflow-auto [scrollbar-gutter:stable_both-edges]">
        <table className="w-full min-w-[1180px] border-separate border-spacing-0 text-sm">
          <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
            <tr>
              <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                <SortableTableHeader
                  field="merchant"
                  label="Merchant"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
              </th>
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
                  field="total"
                  label="Total"
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
                  field="avg"
                  label="Avg ticket"
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
                  colSpan={8}
                  className="px-3 py-10 text-center text-sm text-text-muted"
                >
                  Loading merchant levers...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td
                  colSpan={8}
                  className="px-3 py-10 text-center text-sm text-text-muted"
                >
                  No merchant levers in this timeframe.
                </td>
              </tr>
            ) : (
              displayRows.map((row) => (
                <tr
                  key={row.merchant}
                  className="border-b border-border/30 align-top transition-colors hover:bg-surface-muted/20"
                >
                  <td className="border-b border-border/20 px-3 py-2.5 font-medium text-text">
                    {row.merchant}
                  </td>
                  <td className="border-b border-border/20 px-3 py-2.5 text-text">
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
                    {formatCurrency(row.totalSpend, { decimals: 2 })}
                  </td>
                  <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                    {totalSpend > 0
                      ? formatPercent((row.totalSpend / totalSpend) * 100, {
                          decimals: 0,
                        })
                      : '—'}
                  </td>
                  <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                    {formatCurrency(row.totalSpend / row.transactionCount, {
                      decimals: 2,
                    })}
                  </td>
                  <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                    {row.transactionCount}
                  </td>
                  <td className="border-b border-border/20 px-3 py-2.5 text-xs text-text-muted">
                    {merchantPlaybook(
                      row.category,
                      row.essentiality,
                      row.transactionCount,
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
