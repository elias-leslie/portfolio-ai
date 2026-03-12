'use client'

import { BarChart3 } from 'lucide-react'
import { Card } from '@/components/ui/card'
import type { PortfolioAnalytics } from '@/lib/api/portfolio'

interface PortfolioStatsProps {
  analytics: PortfolioAnalytics
}

export function PortfolioStats({ analytics }: PortfolioStatsProps) {
  const avgInvestedPositionSize =
    analytics.numPositions > 0
      ? analytics.portfolioValue.totalValue / analytics.numPositions
      : 0

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value)
  }

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-accent" />
        <h3 className="text-sm font-semibold text-text">Portfolio Stats</h3>
      </div>

      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-muted">Total Positions</span>
          <span className="text-sm font-medium text-text">
            {analytics.numPositions}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-muted">Unique Symbols</span>
          <span className="text-sm font-medium text-text">
            {analytics.numSymbols}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-muted">
            Avg Invested Position Size
          </span>
          <span className="text-sm font-medium text-text">
            {formatCurrency(avgInvestedPositionSize)}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-muted">Invested Value</span>
          <span className="text-sm font-medium text-text">
            {formatCurrency(analytics.portfolioValue.totalValue)}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-muted">Cash Reserve</span>
          <span className="text-sm font-medium text-text">
            {formatCurrency(analytics.cashBalanceTotal)}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-muted">Largest Position</span>
          <span className="text-sm font-medium text-text">
            {analytics.concentration.topHoldingPct.toFixed(1)}%
          </span>
        </div>
        <div className="border-t border-border pt-3">
          <div className="flex justify-between items-center">
            <span className="text-sm text-text-muted">Return Quality</span>
            {analytics.sharpeRatio !== null && Number.isFinite(analytics.sharpeRatio) ? (
              <span
                className={`text-sm font-medium ${
                  analytics.sharpeRatio >= 1
                    ? 'text-gain'
                    : analytics.sharpeRatio >= 0
                      ? 'text-accent'
                      : 'text-loss'
                }`}
              >
                {analytics.sharpeRatio.toFixed(2)}
              </span>
            ) : (
              <span className="text-sm font-medium text-text-muted">Unavailable</span>
            )}
          </div>
          <p className="mt-1 text-xs text-text-muted">
            {analytics.sharpeRatio !== null && Number.isFinite(analytics.sharpeRatio)
              ? 'Higher means your returns have been steadier for the amount of risk taken.'
              : 'This needs enough portfolio history to judge fairly, so the app is holding it back for now.'}
          </p>
        </div>
      </div>
    </Card>
  )
}
