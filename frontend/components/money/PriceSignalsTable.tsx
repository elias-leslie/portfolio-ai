'use client'

import { formatLeverDate } from '@/components/money/lever-helpers'
import { Badge } from '@/components/ui/badge'
import type { HouseholdPriceInsight } from '@/lib/api/household'
import {
  formatCurrency,
  formatEnumLabel,
  formatPercent,
} from '@/lib/formatters'

interface PriceSignalsTableProps {
  rows: HouseholdPriceInsight[]
}

export function PriceSignalsTable({ rows }: PriceSignalsTableProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border/40 bg-surface/45">
      <div className="max-h-[32vh] overflow-auto [scrollbar-gutter:stable_both-edges]">
        <table className="w-full min-w-[1180px] border-separate border-spacing-0 text-sm">
          <thead className="sticky top-0 z-20 bg-bg/95 backdrop-blur">
            <tr>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Item
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Merchant
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Signal
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Latest
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Prior
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Delta
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-right text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Confidence
              </th>
              <th className="border-b border-border/40 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.16em] text-text-muted/80">
                Notes
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
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
