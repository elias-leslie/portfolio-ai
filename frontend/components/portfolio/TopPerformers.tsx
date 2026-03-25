'use client'

import { TrendingDown, TrendingUp } from 'lucide-react'
import { Card } from '@/components/ui/card'
import type { PositionPerformance } from '@/lib/api/portfolio'
import { formatCurrency, formatPercent } from '@/lib/formatters'

interface TopPerformersProps {
  topPerformers: PositionPerformance[]
  bottomPerformers: PositionPerformance[]
}

export function TopPerformers({
  topPerformers,
  bottomPerformers,
}: TopPerformersProps) {
  return (
    <Card className="p-6">
      <h3 className="mb-4 font-display italic text-lg tracking-tight text-text">Top Performers</h3>
      <div className="space-y-6">
        {/* Winners */}
        <div>
          <div className="mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-gain" />
            <span className="text-xs font-medium text-text-muted">
              Best Performers
            </span>
          </div>
          <div className="space-y-2">
            {topPerformers.length > 0 ? (
              topPerformers.map((position, index) => (
                <div
                  key={`top-${index}-${position.symbol}`}
                  className="flex items-center justify-between rounded-lg px-3 py-2 transition-colors duration-150 hover:bg-surface-muted/20"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-medium tabular-nums text-text">
                      {position.symbol}
                    </span>
                    <span className="text-xs text-text-muted">
                      {position.weightPct.toFixed(1)}%
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium tabular-nums text-gain">
                      {formatPercent(position.gainPct, { decimals: 2, sign: true })}
                    </div>
                    <div className="text-xs tabular-nums text-text-muted">
                      {formatCurrency(position.gainAmount)}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-lg bg-surface-muted/10 px-3 py-2 text-sm text-text-muted">No performers with enough history yet</div>
            )}
          </div>
        </div>

        {/* Divider */}
        <div className="border-t border-border/40" />

        {/* Losers */}
        <div>
          <div className="mb-3 flex items-center gap-2">
            <TrendingDown className="h-4 w-4 text-loss" />
            <span className="text-xs font-medium text-text-muted">
              Worst Performers
            </span>
          </div>
          <div className="space-y-2">
            {bottomPerformers.length > 0 ? (
              bottomPerformers.map((position, index) => (
                <div
                  key={`bottom-${index}-${position.symbol}`}
                  className="flex items-center justify-between rounded-lg px-3 py-2 transition-colors duration-150 hover:bg-surface-muted/20"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-medium tabular-nums text-text">
                      {position.symbol}
                    </span>
                    <span className="text-xs text-text-muted">
                      {position.weightPct.toFixed(1)}%
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium tabular-nums text-loss">
                      {formatPercent(position.gainPct, { decimals: 2, sign: true })}
                    </div>
                    <div className="text-xs tabular-nums text-text-muted">
                      {formatCurrency(position.gainAmount)}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-lg bg-surface-muted/10 px-3 py-2 text-sm text-text-muted">No performers with enough history yet</div>
            )}
          </div>
        </div>
      </div>
    </Card>
  )
}
