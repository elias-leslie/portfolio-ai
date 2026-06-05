'use client'

import { type MouseEvent, useState } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/lib/utils'

export interface TrendDatum {
  date: string | null
  value: number
}

interface TrendSparklineProps {
  points: TrendDatum[]
  width?: number
  height?: number
  strokeWidth?: number
  className?: string
  /** Formats the hovered value for the tooltip (e.g. `$311.80` or `Score 61`). */
  formatValue: (value: number) => string
  /** Accessible description prefix, e.g. "AAPL 1M price". */
  ariaLabel: string
}

function formatTooltipDate(iso: string | null): string | null {
  if (!iso) return null
  // A bare date (YYYY-MM-DD) is a daily/weekly close; a full ISO timestamp is an
  // intraday bar, shown as its market (ET) time of day rather than the date.
  const hasTime = iso.length > 10
  const parsed = new Date(hasTime ? iso : `${iso}T00:00:00Z`)
  if (Number.isNaN(parsed.getTime())) return null
  if (hasTime) {
    return parsed.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      timeZone: 'America/New_York',
    })
  }
  return parsed.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: '2-digit',
    timeZone: 'UTC',
  })
}

/**
 * Compact, hover-interactive price/score trendline.
 *
 * Auto-colors gain/loss by first-vs-last value (matching the static Sparkline).
 * On hover it snaps a crosshair to the nearest point and shows the value + date
 * in a portal tooltip (portal so the table's `overflow-hidden` can't clip it).
 */
export function TrendSparkline({
  points,
  width = 56,
  height = 18,
  strokeWidth = 1.5,
  className,
  formatValue,
  ariaLabel,
}: TrendSparklineProps) {
  const [hover, setHover] = useState<{
    index: number
    left: number
    top: number
  } | null>(null)

  if (!points || points.length === 0) {
    return (
      <span
        className={cn(
          'inline-flex items-center justify-center text-[10px] text-text-muted/60',
          className,
        )}
        style={{ width, height }}
        aria-label={`${ariaLabel} unavailable`}
      >
        —
      </span>
    )
  }

  const values = points.map((point) => point.value)
  const minValue = Math.min(...values)
  const maxValue = Math.max(...values)
  const range = maxValue - minValue
  const isFlat = range === 0

  const coords = points.map((point, index) => {
    const x =
      points.length === 1 ? width / 2 : (index / (points.length - 1)) * width
    const y = isFlat
      ? height / 2
      : height - ((point.value - minValue) / range) * height
    return { x, y }
  })

  const pathData = coords
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x},${point.y}`)
    .join(' ')

  const first = values[0]
  const last = values[values.length - 1]
  const trend = last > first ? 'gain' : last < first ? 'loss' : 'neutral'
  const strokeClass =
    trend === 'gain'
      ? 'stroke-gain'
      : trend === 'loss'
        ? 'stroke-loss'
        : 'stroke-viz-3'
  const dotClass =
    trend === 'gain'
      ? 'fill-gain'
      : trend === 'loss'
        ? 'fill-loss'
        : 'fill-viz-3'

  const handleMove = (event: MouseEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const localX = event.clientX - rect.left
    const ratio = width === 0 ? 0 : localX / width
    const index = Math.min(
      points.length - 1,
      Math.max(0, Math.round(ratio * (points.length - 1))),
    )
    const point = coords[index]
    setHover({
      index,
      left: rect.left + point.x,
      top: rect.top + point.y,
    })
  }

  const hovered = hover ? points[hover.index] : null
  const hoveredDate = hovered ? formatTooltipDate(hovered.date) : null

  return (
    <span className={cn('relative inline-flex', className)}>
      <svg
        width={width}
        height={height}
        className="overflow-visible"
        role="img"
        aria-label={`${ariaLabel}, ${points.length} points, trending ${trend}`}
        onMouseMove={handleMove}
        onMouseLeave={() => setHover(null)}
      >
        <rect width={width} height={height} fill="transparent" />
        <path
          d={pathData}
          fill="none"
          className={strokeClass}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle
          cx={coords[coords.length - 1].x}
          cy={coords[coords.length - 1].y}
          r={strokeWidth * 1.4}
          className={dotClass}
        />
        {hover ? (
          <>
            <line
              x1={coords[hover.index].x}
              y1={0}
              x2={coords[hover.index].x}
              y2={height}
              className="stroke-text-muted/40"
              strokeWidth={0.75}
            />
            <circle
              cx={coords[hover.index].x}
              cy={coords[hover.index].y}
              r={strokeWidth * 1.6}
              className={dotClass}
            />
          </>
        ) : null}
      </svg>
      {hover && hovered && typeof document !== 'undefined'
        ? createPortal(
            <span
              className="pointer-events-none fixed z-50 -translate-x-1/2 -translate-y-full rounded-md border border-border/60 bg-surface px-2 py-1 text-[11px] font-medium tabular-nums text-text shadow-lg"
              style={{ left: hover.left, top: hover.top - 6 }}
            >
              {formatValue(hovered.value)}
              {hoveredDate ? (
                <span className="ml-1 text-text-muted">· {hoveredDate}</span>
              ) : null}
            </span>,
            document.body,
          )
        : null}
    </span>
  )
}
