'use client'

import { merchantPlaybook } from '@/components/money/lever-helpers'
import type { MerchantAggregate } from '@/components/money/merchant-aggregation'
import { Badge } from '@/components/ui/badge'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'

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
  return (
    <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
      <div className="max-h-[40vh] overflow-auto [scrollbar-gutter:stable_both-edges]">
        <table className="w-full min-w-[1180px] border-separate border-spacing-0 text-sm">
          <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
            <tr>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Merchant
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Category
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Type
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Total
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Share
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Avg ticket
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Tx
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
              rows.slice(0, 50).map((row) => (
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
