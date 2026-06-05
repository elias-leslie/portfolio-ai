'use client'

import type { PriceTrend } from '@/lib/api/watchlist'
import { cn } from '@/lib/utils'
import { TrendSparkline } from './TrendSparkline'

const ORDER = ['D', 'W', 'Q', 'Y'] as const
const FULL_NAME: Record<string, string> = {
  D: 'Daily',
  W: 'Weekly',
  Q: 'Quarterly',
  Y: 'Yearly',
}

function formatPrice(value: number): string {
  return `$${value.toFixed(2)}`
}

function returnLabel(trend: PriceTrend): string {
  if (
    typeof trend.returnPct !== 'number' ||
    !Number.isFinite(trend.returnPct)
  ) {
    return 'no return yet'
  }
  const pct = trend.returnPct
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(pct === 0 || Math.abs(pct) >= 10 ? 0 : 1)}%`
}

/**
 * The four rolling price trendlines (Daily 1M, Weekly 3M, Quarterly 6M, Yearly
 * 1Y) for a scanner row, laid out as a compact 2x2 grid. Young symbols draw a
 * shorter line plus an amber "young" dot; timeframes with no drawable history
 * fall back to an em dash.
 */
export function PriceTrendSparklines({
  trends,
  symbol,
  className,
}: {
  trends?: PriceTrend[]
  symbol: string
  className?: string
}) {
  const byKey = new Map((trends ?? []).map((trend) => [trend.key, trend]))

  return (
    <div className={cn('grid grid-cols-2 gap-x-2.5 gap-y-1', className)}>
      {ORDER.map((key) => {
        const trend = byKey.get(key)
        const points =
          trend?.series?.map((point) => ({
            date: point.date,
            value: point.close,
          })) ?? []
        const drawable = points.length >= 2
        const title = `${FULL_NAME[key]} — last ${trend?.label ?? '—'}: ${
          trend ? returnLabel(trend) : 'unavailable'
        }${trend?.partial ? ` · young (${trend.pointCount} pts)` : ''}`

        return (
          <div key={key} className="flex items-center gap-1" title={title}>
            <span className="flex w-3 items-center text-[9px] font-semibold uppercase tracking-wide text-text-muted">
              {key}
              {trend?.partial ? (
                <span
                  className="ml-0.5 h-1 w-1 shrink-0 rounded-full bg-warning"
                  aria-hidden
                />
              ) : null}
            </span>
            {drawable ? (
              <TrendSparkline
                points={points}
                formatValue={formatPrice}
                ariaLabel={`${symbol} ${FULL_NAME[key]} price`}
              />
            ) : (
              <span
                className="inline-flex h-[18px] w-[56px] items-center justify-center text-[10px] text-text-muted/60"
                aria-label={`${symbol} ${FULL_NAME[key]} price unavailable`}
              >
                —
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}
