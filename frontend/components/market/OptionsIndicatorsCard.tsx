'use client'

import { Info, Loader2, Minus, TrendingDown, TrendingUp } from 'lucide-react'
import { Card } from '@/components/ui/card'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { useMarketIntelligence } from '@/lib/hooks/useMarketIntelligence'
import { formatRelativeTime } from '@/lib/utils'

const SIGNAL_COLORS: Record<string, string> = {
  Bullish: 'text-gain',
  Neutral: 'text-text-muted',
  Bearish: 'text-loss',
}

const SIGNAL_BG: Record<string, string> = {
  Bullish: 'bg-gain/10',
  Neutral: 'bg-surface-muted',
  Bearish: 'bg-loss/10',
}

function TrendIcon({
  trend,
}: {
  trend: 'up' | 'down' | 'flat' | null | undefined
}) {
  if (trend === 'up') return <TrendingUp className="h-3 w-3 text-loss" />
  if (trend === 'down') return <TrendingDown className="h-3 w-3 text-gain" />
  return <Minus className="h-3 w-3 text-text-muted" />
}

export function OptionsIndicatorsCard() {
  const { data, isLoading, error } = useMarketIntelligence()

  if (isLoading) {
    return (
      <Card className="p-4">
        <div className="flex items-center justify-center h-24">
          <Loader2 className="h-5 w-5 animate-spin text-text-muted" />
        </div>
      </Card>
    )
  }

  if (error || !data) {
    return (
      <Card className="p-4">
        <div className="text-sm text-text-muted">
          Unable to load options data
        </div>
      </Card>
    )
  }

  const putcall = data.indicators?.putcall
  const optionsActivity = data.optionsActivity

  // If no options data at all, don't render
  if (!putcall && !optionsActivity) {
    return null
  }

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text">
          Options Market Sentiment
        </h3>
        {putcall?.lastUpdated && (
          <span className="text-xs text-text-muted">
            {formatRelativeTime(putcall.lastUpdated)}
          </span>
        )}
      </div>

      <div className="space-y-3">
        {/* Put/Call Ratio */}
        {putcall && (
          <div className="flex items-center justify-between p-3 rounded-lg bg-surface-muted/40 border border-border/50">
            <div className="flex items-center gap-2">
              <span className="text-lg">{putcall.emoji}</span>
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium text-text">
                    Put/Call Ratio
                  </span>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger>
                        <Info className="h-3 w-3 text-text-muted" />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        <p className="text-xs">{putcall.tooltip}</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-lg font-semibold text-text">
                    {putcall.value.toFixed(2)}
                  </span>
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded ${SIGNAL_BG[putcall.signal]} ${SIGNAL_COLORS[putcall.signal]}`}
                  >
                    {putcall.signal}
                  </span>
                </div>
              </div>
            </div>

            {/* Context: Trend & Percentile */}
            {putcall.context && (
              <div className="text-right">
                <div className="flex items-center gap-1 justify-end">
                  <TrendIcon trend={putcall.context.trend} />
                  <span className="text-xs text-text-muted">
                    {putcall.context.trendPct > 0 ? '+' : ''}
                    {putcall.context.trendPct.toFixed(1)}% 7d
                  </span>
                </div>
                <div className="text-xs text-text-muted mt-0.5">
                  {putcall.context.percentileRank}th percentile (90d)
                </div>
              </div>
            )}
          </div>
        )}

        {/* Options Activity Metrics */}
        {optionsActivity && (
          <div className="grid grid-cols-2 gap-2">
            {/* Near-Term Activity */}
            <div className="p-2 rounded-lg bg-surface-muted/30 border border-border/30">
              <div className="text-xs text-text-muted">Near-Term Options</div>
              <div className="flex items-baseline gap-1 mt-0.5">
                <span className="text-sm font-medium text-text">
                  {optionsActivity.nearTermPct.toFixed(0)}%
                </span>
                <span className="text-xs text-text-muted">
                  ({optionsActivity.nearTermSignal})
                </span>
              </div>
            </div>

            {/* Concentration */}
            <div className="p-2 rounded-lg bg-surface-muted/30 border border-border/30">
              <div className="text-xs text-text-muted">Top 5 Concentration</div>
              <div className="flex items-baseline gap-1 mt-0.5">
                <span className="text-sm font-medium text-text">
                  {optionsActivity.concentrationPct.toFixed(0)}%
                </span>
                <span className="text-xs text-text-muted">
                  ({optionsActivity.concentrationSignal})
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Top Sectors if available */}
        {optionsActivity?.topSectors &&
          optionsActivity.topSectors.length > 0 && (
            <div className="pt-2 border-t border-border/30">
              <div className="text-xs text-text-muted mb-1">Active Sectors</div>
              <div className="flex flex-wrap gap-1">
                {optionsActivity.topSectors.slice(0, 5).map((s) => (
                  <span
                    key={s.sector}
                    className="text-xs px-2 py-0.5 rounded bg-surface-muted border border-border/50 text-text-muted"
                  >
                    {s.sector} {s.weightPct.toFixed(0)}%
                  </span>
                ))}
              </div>
            </div>
          )}
      </div>
    </Card>
  )
}
