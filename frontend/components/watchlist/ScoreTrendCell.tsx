'use client'

import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { WatchlistItem } from '@/lib/api/watchlist'
import { getScoreBadgeVariant } from './ExpandedRowUtils'
import { TrendSparkline } from './TrendSparkline'

function roundScore(value?: number | null): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toFixed(0)
    : '—'
}

/**
 * Score column for the scanner: the current overall score plus an interactive
 * score trendline (built the same way as the price trendlines). Hover the line
 * to read the score and date at each daily snapshot. Replaces the old static
 * meter and the score sparkline that used to live in the expanded row.
 */
export function ScoreTrendCell({
  item,
  width = 64,
  height = 20,
}: {
  item: WatchlistItem
  width?: number
  height?: number
}) {
  const score = item.currentScore
  if (!score) return <span className="text-text-muted">—</span>

  const overall = roundScore(score.overall)
  const priceScore = roundScore(score.price?.score)
  const technicalScore = roundScore(score.technical?.score)
  const stale = score.price?.stale || score.technical?.stale

  const points =
    item.scoreTrend?.series
      ?.filter(
        (point) =>
          typeof point.value === 'number' && Number.isFinite(point.value),
      )
      .map((point) => ({ date: point.date, value: point.value })) ?? []

  return (
    <div className="inline-flex items-center gap-2">
      <TooltipProvider delayDuration={120}>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-flex cursor-help items-center gap-1">
              <Badge
                variant={getScoreBadgeVariant(score.overall)}
                className="font-mono tabular-nums"
              >
                {overall}
              </Badge>
              {stale ? (
                <span
                  className="h-1.5 w-1.5 rounded-full bg-warning"
                  aria-label="Score inputs stale"
                />
              ) : null}
            </span>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs text-xs leading-5">
            Scanner score {overall} (price {priceScore}, technical{' '}
            {technicalScore}). Line shows the recent daily score trend — hover
            for score and date. This is a scanner score, not a trade
            instruction.
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
      {points.length >= 2 ? (
        <TrendSparkline
          points={points}
          width={width}
          height={height}
          formatValue={(value) => `Score ${Math.round(value)}`}
          ariaLabel={`${item.symbol} score`}
        />
      ) : (
        <span
          className="inline-flex items-center justify-center text-[10px] text-text-muted/60"
          style={{ width, height }}
          aria-label={`${item.symbol} score trend building`}
        >
          —
        </span>
      )}
    </div>
  )
}
