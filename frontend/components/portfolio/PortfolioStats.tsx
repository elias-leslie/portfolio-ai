'use client'

import { BarChart3 } from 'lucide-react'
import { Card } from '@/components/ui/card'
import type { PortfolioAnalytics } from '@/lib/api/portfolio'

interface PortfolioStatsProps {
  analytics: PortfolioAnalytics
}

export function PortfolioStats({ analytics }: PortfolioStatsProps) {
  // Calculate average position size
  const avgPositionSize =
    analytics.numPositions > 0
      ? analytics.portfolioValue.totalValue / analytics.numPositions
      : 0

  // Find largest position
  const largestPosition =
    analytics.topPerformers.length > 0
      ? Math.max(...analytics.topPerformers.map((p) => p.weightPct))
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
          <span className="text-sm text-text-muted">Avg Position Size</span>
          <span className="text-sm font-medium text-text">
            {formatCurrency(avgPositionSize)}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-text-muted">Largest Position</span>
          <span className="text-sm font-medium text-text">
            {largestPosition.toFixed(1)}%
          </span>
        </div>
        {analytics.sharpeRatio !== null && (
          <div className="flex justify-between items-center border-t border-border pt-3">
            <span className="text-sm text-text-muted">Sharpe Ratio</span>
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
          </div>
        )}
      </div>
    </Card>
  )
}
