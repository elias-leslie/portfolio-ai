/**
 * MarketIntelligence Component
 *
 * Visual-first market conditions display:
 * - Market Movers (top gainers/losers) + Sector Movers at top
 * - Market Sentiment trend chart (Fear & Greed + News + P/C Ratio)
 * - Key Indicators trend chart (S&P 500, VIX, 10Y, Dollar)
 * - Sector Performance chart
 */

'use client'

import { LoadErrorState } from '@/components/shared/LoadErrorState'
import { Card } from '@/components/ui/card'
import { useMarketIntelligence } from '@/lib/hooks/useMarketIntelligence'
import { IndicatorsTrendChart } from './IndicatorsTrendChart'
import { MarketMoversTable } from './MarketMoversTable'
import { SectorMoversTable } from './SectorMoversTable'
import { SectorPerformanceChart } from './SectorPerformanceChart'
import { SentimentTrendChart } from './SentimentTrendChart'

export function MarketIntelligence() {
  const { data, isLoading, error, refetch, isFetching } = useMarketIntelligence()

  if (isLoading) {
    return (
      <Card className="p-6 shadow-lg">
        <div className="space-y-6 animate-pulse">
          <div className="h-24 bg-surface-muted/60 rounded-xl" />
          <div className="h-48 bg-surface-muted/60 rounded-xl" />
          <div className="h-48 bg-surface-muted/60 rounded-xl" />
          <div className="h-64 bg-surface-muted/60 rounded-xl" />
        </div>
      </Card>
    )
  }

  if (error || !data) {
    return (
      <Card className="p-6 shadow-lg">
        <LoadErrorState
          title="Failed to load market intelligence."
          detail="Retry to refresh market conditions, sector rotation, and the related charts."
          onRetry={() => {
            void refetch()
          }}
          isRetrying={isFetching}
          className="py-4"
        />
      </Card>
    )
  }

  const { fearGreed, sectorRotation, lastUpdated } = data

  return (
    <Card className="p-6 shadow-lg">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-lg font-semibold tracking-tight text-text">
          Market Conditions
        </h2>
        {lastUpdated ? (
          <span className="text-xs text-text-muted">
            Updated {new Date(lastUpdated).toLocaleString('en-US', {
              month: 'short',
              day: 'numeric',
              hour: 'numeric',
              minute: '2-digit',
            })}
          </span>
        ) : null}
      </div>

      {/* Fear & Greed Alert if stale */}
      {fearGreed.isStale && (
        <div className="mb-4 px-3 py-2 bg-warning/10 border border-warning/30 rounded-lg text-xs text-warning">
          Fear & Greed data is {fearGreed.ageDays} days old. Market may have
          changed.
        </div>
      )}

      {/* Top Section: Market Movers (Stocks) + Sector Movers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Stock Movers */}
        <div className="bg-surface-muted/30 rounded-xl p-4 border border-border/30">
          <MarketMoversTable />
        </div>

        {/* Sector Movers */}
        <div className="bg-surface-muted/30 rounded-xl p-4 border border-border/30">
          <SectorMoversTable
            leading={sectorRotation.leading}
            neutral={sectorRotation.neutral}
            lagging={sectorRotation.lagging}
            lastUpdated={lastUpdated}
          />
        </div>
      </div>

      {/* Charts Section */}
      <div className="space-y-8">
        {/* Sentiment Trend */}
        <div className="relative">
          <SentimentTrendChart />
        </div>

        {/* Key Indicators */}
        <div>
          <IndicatorsTrendChart />
        </div>

        {/* Sector Performance */}
        <div>
          <SectorPerformanceChart />
        </div>
      </div>
    </Card>
  )
}
