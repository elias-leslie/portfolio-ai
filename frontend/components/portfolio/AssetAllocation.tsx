'use client'

import { PieChart } from 'lucide-react'
import { Card } from '@/components/ui/card'
import type { PositionPerformance } from '@/lib/api/portfolio'
import { cn } from '@/lib/utils'
import { formatCurrencyWhole } from './portfolio-utils'

interface AssetAllocationProps {
  topPerformers: PositionPerformance[]
}

export function AssetAllocation({ topPerformers }: AssetAllocationProps) {
  // Sort by weight to show largest holdings
  const topHoldings = [...topPerformers]
    .sort((a, b) => b.weightPct - a.weightPct)
    .slice(0, 5)

  const getBarColor = (index: number) => {
    const colors = [
      'bg-primary',
      'bg-accent',
      'bg-warning',
      'bg-chart-cyan',
      'bg-gain',
    ]
    return colors[index % colors.length]
  }

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2">
        <PieChart className="h-4 w-4 text-accent" />
        <h3 className="font-display italic text-lg tracking-tight text-text">Top Holdings</h3>
      </div>

      <div className="space-y-4">
        {topHoldings.length > 0 ? (
          topHoldings.map((position, index) => (
            <div key={`holding-${index}-${position.symbol}`}>
              <div className="mb-1 flex items-center justify-between">
                <span className="font-medium text-text">{position.symbol}</span>
                <span className="text-sm text-text-muted">
                  {position.weightPct.toFixed(1)}%
                </span>
              </div>
              <div className="mb-1 h-2 w-full overflow-hidden rounded-full bg-surface-muted">
                <div
                  className={cn('h-full transition-all duration-500', getBarColor(index))}
                  style={{ width: `${position.weightPct}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-xs text-text-muted">
                <span>{formatCurrencyWhole(position.currentValue)}</span>
                <span
                  className={position.gainPct >= 0 ? 'text-gain' : 'text-loss'}
                >
                  {position.gainPct >= 0 ? '+' : ''}
                  {position.gainPct.toFixed(1)}%
                </span>
              </div>
            </div>
          ))
        ) : (
          <div className="py-8 text-center text-sm text-text-muted">
            No holdings data available
          </div>
        )}
      </div>
    </Card>
  )
}
