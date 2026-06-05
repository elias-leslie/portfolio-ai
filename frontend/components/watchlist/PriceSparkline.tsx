'use client'

import { Sparkline } from '@/components/ui/sparkline'
import { useScoreHistory } from '@/lib/hooks/useWatchlist'

interface PriceSparklineProps {
  itemId: string
  width?: number
  height?: number
  className?: string
}

/**
 * Compact price sparkline for a scanner row.
 *
 * Reuses the score-history endpoint (which now carries the per-point close
 * price) and plots the price series. The Sparkline primitive auto-colors
 * gain/loss by first-vs-last value. Degrades to an em dash when no price
 * series is available (sparse refresh history is harmless).
 */
export function PriceSparkline({
  itemId,
  width = 64,
  height = 20,
  className,
}: PriceSparklineProps) {
  const { data: historyResponse, isLoading, error } = useScoreHistory(itemId)

  if (isLoading) {
    return (
      <div
        className="animate-pulse rounded bg-surface-muted"
        style={{ width, height }}
        aria-label="Loading price history"
      />
    )
  }

  const prices =
    historyResponse?.history
      ?.map((point) => point.price)
      .filter(
        (price): price is number =>
          typeof price === 'number' && Number.isFinite(price),
      ) ?? []

  if (error || prices.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-xs text-text-muted"
        style={{ width, height }}
        aria-label="Price history unavailable"
      >
        —
      </div>
    )
  }

  return (
    <Sparkline
      data={prices}
      width={width}
      height={height}
      className={className}
    />
  )
}
