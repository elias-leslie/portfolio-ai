'use client'

import {
  categoryPlaybook,
  trimRateForCategory,
} from '@/components/money/lever-helpers'
import { Badge } from '@/components/ui/badge'
import type { HouseholdSpendingCategory } from '@/lib/api/household'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'

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
  return (
    <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
      <div className="max-h-[34vh] overflow-auto [scrollbar-gutter:stable_both-edges]">
        <table className="w-full min-w-[1100px] border-separate border-spacing-0 text-sm">
          <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
            <tr>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Category
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Type
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Monthly
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Share
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Tx
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Modeled trim
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Move
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
              rows.map((row: HouseholdSpendingCategory) => {
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
