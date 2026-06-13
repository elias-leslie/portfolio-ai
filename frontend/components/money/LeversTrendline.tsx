'use client'

import { type MouseEvent, useState } from 'react'
import { createPortal } from 'react-dom'
import { formatCurrency } from '@/lib/formatters'
import { cn } from '@/lib/utils'
import type { TrendSeries } from './levers-action-model'

interface LeversTrendlineProps {
  series: TrendSeries[]
  width?: number
  height?: number
  className?: string
}

const STROKES = ['stroke-loss', 'stroke-warning', 'stroke-viz-3', 'stroke-gain']
const FILLS = ['fill-loss', 'fill-warning', 'fill-viz-3', 'fill-gain']

function formatDate(value: string) {
  const isoValue =
    value.length === 7
      ? `${value}-01T00:00:00Z`
      : value.length === 10
        ? `${value}T00:00:00Z`
        : value
  const parsed = new Date(isoValue)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString('en-US', {
    month: 'short',
    year: '2-digit',
    timeZone: 'UTC',
  })
}

export function LeversTrendline({
  series,
  width = 520,
  height = 180,
  className,
}: LeversTrendlineProps) {
  const [hover, setHover] = useState<{
    index: number
    x: number
    left: number
    top: number
  } | null>(null)

  const activeSeries = series
    .filter((item) => item.points.length > 0)
    .slice(0, 4)
  if (activeSeries.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border/40 bg-surface-muted/10 p-6 text-sm text-text-muted">
        Trendlines appear after enough recurring-item or category history
        exists.
      </div>
    )
  }

  const allValues = activeSeries.flatMap((item) =>
    item.points.map((point) => point.value),
  )
  const maxPoints = Math.max(...activeSeries.map((item) => item.points.length))
  const minValue = Math.min(0, ...allValues)
  const maxValue = Math.max(...allValues)
  const range = maxValue - minValue || 1
  const padX = 20
  const padY = 16
  const chartWidth = width - padX * 2
  const chartHeight = height - padY * 2

  function coord(value: number, index: number) {
    return {
      x:
        maxPoints === 1
          ? width / 2
          : padX + (index / (maxPoints - 1)) * chartWidth,
      y: padY + chartHeight - ((value - minValue) / range) * chartHeight,
    }
  }

  const paths = activeSeries.map((item) => {
    const coords = item.points.map((point, index) => coord(point.value, index))
    return {
      item,
      coords,
      d: coords
        .map(
          (point, index) => `${index === 0 ? 'M' : 'L'} ${point.x},${point.y}`,
        )
        .join(' '),
    }
  })

  function handleMove(event: MouseEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect()
    const localX = event.clientX - rect.left - padX
    const ratio = chartWidth === 0 ? 0 : localX / chartWidth
    const index = Math.min(
      maxPoints - 1,
      Math.max(0, Math.round(ratio * (maxPoints - 1))),
    )
    const x = padX + (index / Math.max(1, maxPoints - 1)) * chartWidth
    setHover({
      index,
      x,
      left: rect.left + x,
      top: rect.top + padY,
    })
  }

  const hoveredRows = hover
    ? activeSeries
        .map((item) => ({
          item,
          point: item.points[Math.min(hover.index, item.points.length - 1)],
        }))
        .filter((row) => row.point)
    : []
  const hoveredDate = hoveredRows[0]?.point.date

  return (
    <div className={cn('space-y-3', className)}>
      <svg
        width="100%"
        viewBox={`0 0 ${width} ${height}`}
        className="overflow-visible"
        role="img"
        aria-label={`${activeSeries.length} savings trendlines`}
        onMouseMove={handleMove}
        onMouseLeave={() => setHover(null)}
      >
        <rect width={width} height={height} fill="transparent" />
        <line
          x1={padX}
          y1={padY + chartHeight}
          x2={width - padX}
          y2={padY + chartHeight}
          className="stroke-border/40"
          strokeWidth={1}
        />
        {paths.map((path, index) => (
          <g key={path.item.id}>
            <path
              d={path.d}
              fill="none"
              className={STROKES[index % STROKES.length]}
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {path.coords.map((point, pointIndex) => (
              <circle
                key={`${path.item.id}-${pointIndex}`}
                cx={point.x}
                cy={point.y}
                r={hover?.index === pointIndex ? 3.5 : 2.2}
                className={FILLS[index % FILLS.length]}
              />
            ))}
          </g>
        ))}
        {hover ? (
          <line
            x1={hover.x}
            y1={padY}
            x2={hover.x}
            y2={padY + chartHeight}
            className="stroke-text-muted/40"
            strokeWidth={0.75}
          />
        ) : null}
      </svg>
      <div className="flex flex-wrap gap-3 text-xs text-text-muted">
        {activeSeries.map((item, index) => (
          <span key={item.id} className="inline-flex items-center gap-1.5">
            <span
              className={cn(
                'h-2 w-2 rounded-full',
                FILLS[index % FILLS.length],
              )}
            />
            {item.label}
          </span>
        ))}
      </div>
      {hover && hoveredRows.length > 0 && typeof document !== 'undefined'
        ? createPortal(
            <div
              className="pointer-events-none fixed z-50 w-max max-w-[260px] -translate-x-1/2 rounded-lg border border-border/60 bg-surface px-3 py-2 text-xs shadow-xl"
              style={{ left: hover.left, top: hover.top }}
            >
              <p className="font-medium text-text">
                {hoveredDate ? formatDate(hoveredDate) : 'Trend point'}
              </p>
              <div className="mt-1 space-y-0.5">
                {hoveredRows.map((row) => (
                  <p
                    key={row.item.id}
                    className="flex items-center justify-between gap-4 text-text-muted"
                  >
                    <span>{row.item.label}</span>
                    <span className="font-mono text-text">
                      {formatCurrency(row.point.value, { decimals: 0 })}
                    </span>
                  </p>
                ))}
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  )
}
