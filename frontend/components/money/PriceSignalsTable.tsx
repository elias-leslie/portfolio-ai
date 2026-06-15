'use client'

import { useMemo, useState } from 'react'
import { formatLeverDate } from '@/components/money/lever-helpers'
import {
  nextSortDirection,
  SortableTableHeader,
  type SortDirection,
} from '@/components/shared/SortableTableHeader'
import { Badge } from '@/components/ui/badge'
import type { HouseholdPriceInsight } from '@/lib/api/household'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'

type PriceSignalSortKey =
  | 'item'
  | 'merchant'
  | 'signal'
  | 'latest'
  | 'prior'
  | 'delta'
  | 'confidence'
  | 'notes'

function compareText(left: string, right: string) {
  return left.localeCompare(right, undefined, { sensitivity: 'base' })
}

function compareNumber(left: number, right: number) {
  return left - right
}

interface PriceSignalsTableProps {
  rows: HouseholdPriceInsight[]
}

export function PriceSignalsTable({ rows }: PriceSignalsTableProps) {
  const [sortKey, setSortKey] = useState<PriceSignalSortKey | null>(null)
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')

  const displayRows = useMemo(() => {
    if (sortKey === null) {
      return rows
    }
    const direction = sortDirection === 'asc' ? 1 : -1
    return [...rows].sort((left, right) => {
      let result = 0
      switch (sortKey) {
        case 'item':
          result = compareText(left.itemName, right.itemName)
          break
        case 'merchant':
          result = compareText(left.merchant, right.merchant)
          break
        case 'signal':
          result = compareText(left.signalType, right.signalType)
          break
        case 'latest':
          result = compareNumber(left.latestPrice, right.latestPrice)
          break
        case 'prior':
          result = compareNumber(left.previousPrice, right.previousPrice)
          break
        case 'delta':
          result = compareNumber(left.priceChange, right.priceChange)
          break
        case 'confidence':
          result = compareNumber(left.confidence, right.confidence)
          break
        case 'notes':
          result = compareText(left.recommendation, right.recommendation)
          break
      }
      return result * direction || compareText(left.itemName, right.itemName)
    })
  }, [rows, sortDirection, sortKey])

  function defaultSortDirection(field: PriceSignalSortKey): SortDirection {
    return ['item', 'merchant', 'signal', 'notes'].includes(field)
      ? 'asc'
      : 'desc'
  }

  function handleSort(field: PriceSignalSortKey) {
    setSortDirection((current) =>
      nextSortDirection(sortKey, field, current, defaultSortDirection(field)),
    )
    setSortKey(field)
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
      <div className="max-h-[32vh] overflow-auto [scrollbar-gutter:stable_both-edges]">
        <table className="w-full min-w-[1180px] border-separate border-spacing-0 text-sm">
          <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
            <tr>
              <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                <SortableTableHeader
                  field="item"
                  label="Item"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
              </th>
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
                  field="signal"
                  label="Signal"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                <SortableTableHeader
                  field="latest"
                  label="Latest"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                  align="right"
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                <SortableTableHeader
                  field="prior"
                  label="Prior"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                  align="right"
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                <SortableTableHeader
                  field="delta"
                  label="Delta"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                  align="right"
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right align-middle">
                <SortableTableHeader
                  field="confidence"
                  label="Confidence"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                  align="right"
                />
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left align-middle">
                <SortableTableHeader
                  field="notes"
                  label="Notes"
                  activeField={sortKey}
                  direction={sortDirection}
                  onSort={handleSort}
                />
              </th>
            </tr>
          </thead>
          <tbody>
            {displayRows.map((row) => (
              <tr
                key={`${row.merchant}-${row.itemName}`}
                className="border-b border-border/30 align-top transition-colors hover:bg-surface-muted/20"
              >
                <td className="border-b border-border/20 px-3 py-2.5 font-medium text-text">
                  {row.itemName}
                </td>
                <td className="border-b border-border/20 px-3 py-2.5 text-text">
                  {row.merchant}
                </td>
                <td className="border-b border-border/20 px-3 py-2.5">
                  <Badge
                    variant={
                      row.signalType === 'shrinkflation'
                        ? 'destructive'
                        : row.signalType === 'price_down'
                          ? 'success'
                          : 'warning'
                    }
                  >
                    {formatEnumLabel(row.signalType)}
                  </Badge>
                </td>
                <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                  {formatCurrency(row.latestPrice, { decimals: 2 })}
                  <div className="text-xs text-text-muted">
                    {formatLeverDate(row.latestDate)}
                  </div>
                </td>
                <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                  {formatCurrency(row.previousPrice, { decimals: 2 })}
                  <div className="text-xs text-text-muted">
                    {formatLeverDate(row.previousDate)}
                  </div>
                </td>
                <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                  {formatCurrency(row.priceChange, { decimals: 2 })}
                  <div className="text-xs text-text-muted">
                    {formatPercent(row.priceChangePct ?? 0, {
                      decimals: 0,
                      sign: true,
                    })}
                  </div>
                </td>
                <td className="border-b border-border/20 px-3 py-2.5 text-right font-mono tabular-nums text-text">
                  {formatPercent(row.confidence * 100, { decimals: 0 })}
                </td>
                <td className="border-b border-border/20 px-3 py-2.5 text-xs text-text-muted">
                  {row.recommendation}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
