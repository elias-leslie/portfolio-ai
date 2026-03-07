'use client'

import { DollarSign, PieChart, RotateCcw, Wallet } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { usePaperTradeSummary } from '@/lib/hooks/usePaperTrades'

type SummaryData = NonNullable<ReturnType<typeof usePaperTradeSummary>['data']>

interface PortfolioBalanceCardsProps {
  summary: SummaryData | undefined
  summaryLoading: boolean
  isResetPending: boolean
  onResetClick: () => void
}

const formatChangeFromStart = (current: number, start: number | undefined): string => {
  if (!start) return '0.00% from start'
  const pct = ((current - start) / start) * 100
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}% from start`
}

export function PortfolioBalanceCards({
  summary,
  summaryLoading,
  isResetPending,
  onResetClick,
}: PortfolioBalanceCardsProps) {
  const fmt = (val: number | undefined) =>
    `$${(val || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

  return (
    <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-muted">Cash Balance</p>
              <p className="text-2xl font-bold">
                {summaryLoading ? '-' : fmt(summary?.cashBalance)}
              </p>
            </div>
            <Wallet className="h-8 w-8 text-primary" suppressHydrationWarning />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-muted">Positions Value</p>
              <p className="text-2xl font-bold">
                {summaryLoading ? '-' : fmt(summary?.positionsValue)}
              </p>
            </div>
            <PieChart className="h-8 w-8 text-accent" suppressHydrationWarning />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-muted">Total Portfolio</p>
              <p className="text-2xl font-bold">
                {summaryLoading ? '-' : fmt(summary?.totalPortfolioValue)}
              </p>
              {summary?.startingBalance && (
                <p
                  className={`text-sm ${(summary?.totalPortfolioValue || 0) >= summary.startingBalance ? 'text-gain' : 'text-loss'}`}
                >
                  {formatChangeFromStart(summary?.totalPortfolioValue || 0, summary.startingBalance)}
                </p>
              )}
            </div>
            <div className="flex flex-col items-end gap-2">
              <DollarSign className="h-8 w-8 text-gain" suppressHydrationWarning />
              <Button
                variant="outline"
                size="sm"
                onClick={onResetClick}
                disabled={isResetPending}
              >
                <RotateCcw className="mr-1 h-3 w-3" suppressHydrationWarning />
                Reset
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
