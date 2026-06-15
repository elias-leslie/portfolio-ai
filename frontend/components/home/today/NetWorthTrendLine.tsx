'use client'

import { type PointerEvent, useState } from 'react'
import { formatCurrencyWhole } from '@/lib/formatters'

export interface TrendPoint {
  date: string
  value: number
}

const CHART_WIDTH = 120
const CHART_HEIGHT = 42

function formatTrendDate(value: string): string {
  const parsed = new Date(`${value}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

function buildTrendPath(
  values: number[],
  width = CHART_WIDTH,
  height = CHART_HEIGHT,
): { d: string; lastY: number; coords: Array<{ x: number; y: number }> } {
  if (values.length === 0) {
    return { d: '', lastY: 0, coords: [] }
  }
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const left = 2
  const right = width - 2
  const top = 5
  const bottom = height - 6
  const step = values.length > 1 ? (right - left) / (values.length - 1) : 0

  let lastY = bottom
  const coords = values.map((value, index) => {
    const x = left + index * step
    const y = bottom - ((value - min) / range) * (bottom - top)
    lastY = y
    return { x, y }
  })
  const d = coords
    .map(
      (coord, index) =>
        `${index === 0 ? 'M' : 'L'} ${coord.x.toFixed(2)} ${coord.y.toFixed(
          2,
        )}`,
    )
    .join(' ')

  return { d, lastY, coords }
}

function trendSummary(points: TrendPoint[]): string {
  if (points.length < 2) {
    return 'History building'
  }
  const first = points[0]
  const last = points[points.length - 1]
  const change = last.value - first.value
  const changePct =
    first.value !== 0 ? (change / Math.abs(first.value)) * 100 : 0
  const sign = change >= 0 ? '+' : ''
  return `${formatTrendDate(first.date)} to ${formatTrendDate(last.date)} · ${sign}${changePct.toFixed(1)}%`
}

export function NetWorthTrendLine({
  points,
  loading,
}: {
  points: TrendPoint[]
  loading: boolean
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null)

  if (loading && points.length === 0) {
    return <div className="mt-2 h-12 rounded-xl skeleton" />
  }
  if (points.length < 2) {
    return null
  }

  const values = points.map((point) => point.value)
  const { d, lastY, coords } = buildTrendPath(values)
  const first = points[0]
  const last = points[points.length - 1]
  const gained = last.value >= first.value
  const active = activeIndex !== null ? points[activeIndex] : null
  const activeCoord = activeIndex !== null ? coords[activeIndex] : null

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    const bounds = event.currentTarget.getBoundingClientRect()
    const viewBoxX =
      ((event.clientX - bounds.left) / bounds.width) * CHART_WIDTH
    let nearest = 0
    for (let index = 1; index < coords.length; index += 1) {
      if (
        Math.abs(coords[index].x - viewBoxX) <
        Math.abs(coords[nearest].x - viewBoxX)
      ) {
        nearest = index
      }
    }
    setActiveIndex(nearest)
  }

  return (
    <div className="relative mt-2 h-14">
      <svg
        role="img"
        aria-label="Net worth trend"
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        className="h-10 w-full overflow-visible"
        preserveAspectRatio="none"
        onPointerMove={handlePointerMove}
        onPointerLeave={() => setActiveIndex(null)}
      >
        <defs>
          <linearGradient
            id="today-net-worth-trend-gradient"
            x1="0"
            x2="1"
            y1="0"
            y2="0"
          >
            <stop offset="0%" stopColor="var(--text-muted)" />
            <stop
              offset="100%"
              stopColor={gained ? 'var(--gain)' : 'var(--loss)'}
            />
          </linearGradient>
        </defs>
        <line
          x1="0"
          x2="120"
          y1="10"
          y2="10"
          stroke="var(--border)"
          strokeOpacity="0.35"
          strokeWidth="0.7"
        />
        <line
          x1="0"
          x2="120"
          y1="30"
          y2="30"
          stroke="var(--border)"
          strokeOpacity="0.25"
          strokeWidth="0.7"
        />
        <path
          d={d}
          fill="none"
          stroke="url(#today-net-worth-trend-gradient)"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2.4"
        />
        {activeCoord ? (
          <>
            <line
              x1={activeCoord.x.toFixed(2)}
              x2={activeCoord.x.toFixed(2)}
              y1="5"
              y2="36"
              stroke="var(--border)"
              strokeOpacity="0.5"
              strokeWidth="0.7"
              strokeDasharray="2 2"
            />
            <circle
              cx={activeCoord.x.toFixed(2)}
              cy={activeCoord.y.toFixed(2)}
              r="2.8"
              fill="var(--text)"
            />
          </>
        ) : null}
        <circle
          cx="118"
          cy={lastY.toFixed(2)}
          r="2.6"
          fill={gained ? 'var(--gain)' : 'var(--loss)'}
        />
      </svg>
      {active && activeCoord ? (
        <div
          data-testid="net-worth-trend-tooltip"
          className="pointer-events-none absolute bottom-full z-50 mb-1 w-max max-w-[180px] -translate-x-1/2 rounded-lg border border-border/50 bg-surface px-3 py-2 text-xs shadow-xl"
          style={{ left: `${(activeCoord.x / CHART_WIDTH) * 100}%` }}
        >
          <p className="font-medium text-text">
            {formatTrendDate(active.date)}
          </p>
          <p className="mt-0.5 font-mono tabular-nums text-text">
            {formatCurrencyWhole(active.value)}
          </p>
        </div>
      ) : null}
      <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
        {trendSummary(points)}
      </p>
    </div>
  )
}
