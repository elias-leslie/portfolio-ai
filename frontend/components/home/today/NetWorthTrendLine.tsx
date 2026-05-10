'use client'

export interface TrendPoint {
  date: string
  value: number
}

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
  width = 120,
  height = 42,
): { d: string; lastY: number } {
  if (values.length === 0) {
    return { d: '', lastY: 0 }
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
  const d = values
    .map((value, index) => {
      const x = left + index * step
      const y = bottom - ((value - min) / range) * (bottom - top)
      lastY = y
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(' ')

  return { d, lastY }
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
  if (loading && points.length === 0) {
    return <div className="mt-2 h-12 rounded-xl skeleton" />
  }
  if (points.length < 2) {
    return null
  }

  const values = points.map((point) => point.value)
  const { d, lastY } = buildTrendPath(values)
  const first = points[0]
  const last = points[points.length - 1]
  const gained = last.value >= first.value

  return (
    <div className="mt-2 h-14">
      <svg
        role="img"
        aria-label="Net worth trend"
        viewBox="0 0 120 42"
        className="h-10 w-full overflow-visible"
        preserveAspectRatio="none"
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
        <circle
          cx="118"
          cy={lastY.toFixed(2)}
          r="2.6"
          fill={gained ? 'var(--gain)' : 'var(--loss)'}
        />
      </svg>
      <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
        {trendSummary(points)}
      </p>
    </div>
  )
}
