'use client'

import { DollarSign, Target, TrendingUp } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import type { usePaperTradeSummary } from '@/lib/hooks/usePaperTrades'
import { formatCurrency, formatPct, getPnlColor } from './tradingFormatters'

type SummaryData = NonNullable<ReturnType<typeof usePaperTradeSummary>['data']>

interface TradingSummaryCardsProps {
  summary: SummaryData | undefined
  summaryLoading: boolean
  openLoading: boolean
  unrealizedPnl: number
}

export function TradingSummaryCards({
  summary,
  summaryLoading,
  openLoading,
  unrealizedPnl,
}: TradingSummaryCardsProps) {
  const winsCount = Math.round(
    ((summary?.winRate || 0) / 100) * (summary?.totalClosed || 0),
  )
  const lossesCount = (summary?.totalClosed || 0) - winsCount

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-muted">Open Positions</p>
              <p className="text-3xl font-bold">
                {summaryLoading ? '-' : summary?.totalOpen || 0}
              </p>
              {!summaryLoading && !openLoading && (
                <p className={`text-sm ${getPnlColor(unrealizedPnl)}`}>
                  {formatCurrency(unrealizedPnl)} unrealized
                </p>
              )}
            </div>
            <TrendingUp className="h-8 w-8 text-primary" suppressHydrationWarning />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-muted">Win Rate</p>
              <p className="text-3xl font-bold">
                {summaryLoading ? '-' : `${(summary?.winRate || 0).toFixed(1)}%`}
              </p>
              {!summaryLoading && (summary?.totalClosed || 0) > 0 && (
                <p className="text-sm text-text-muted">
                  <span className="text-gain">{winsCount}W</span>
                  {' / '}
                  <span className="text-loss">{lossesCount}L</span>
                  {' of '}
                  {summary?.totalClosed} trades
                </p>
              )}
            </div>
            <Target className="h-8 w-8 text-gain" suppressHydrationWarning />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-muted">Total P&L</p>
              <p className={`text-3xl font-bold ${getPnlColor(summary?.totalPnlPct)}`}>
                {summaryLoading ? '-' : formatPct(summary?.totalPnlPct)}
              </p>
              {!summaryLoading && summary && (
                <p
                  className={`text-sm ${getPnlColor((summary.totalPortfolioValue || 0) - (summary.startingBalance || 100000))}`}
                >
                  {formatCurrency(
                    (summary.totalPortfolioValue || 0) - (summary.startingBalance || 100000),
                  )}
                </p>
              )}
            </div>
            <DollarSign
              className={`h-8 w-8 ${getPnlColor(summary?.totalPnlPct)}`}
              suppressHydrationWarning
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-muted">Best / Worst Trade</p>
              <p className={`text-3xl font-bold ${getPnlColor(summary?.bestTradePct)}`}>
                {summaryLoading ? '-' : formatPct(summary?.bestTradePct)}
              </p>
              {!summaryLoading && summary?.worstTradePct !== undefined && (
                <p className="text-sm text-loss">
                  Worst: {formatPct(summary.worstTradePct)}
                </p>
              )}
            </div>
            <TrendingUp className="h-8 w-8 text-gain" suppressHydrationWarning />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
