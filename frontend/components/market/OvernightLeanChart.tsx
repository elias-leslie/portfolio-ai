'use client'

import { Loader2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { OvernightLean } from '@/lib/api/macro'
import type { IndicatorDataPoint } from '@/lib/api/market'
import { useMacroConditions } from '@/lib/hooks/useMacro'
import { useOvernightHistory } from '@/lib/hooks/useMarketIntelligence'
import { cn } from '@/lib/utils'
import { MarketPanelMessage } from './MarketPanelMessage'
import {
  DEFAULT_MARKET_TIMEFRAME,
  formatChartDate,
  type Timeframe,
  TimeframeSelector,
  timeframeToDays,
} from './TimeframeSelector'
import {
  ImpactCard,
  type ImpactMetric,
  type ImpactTone,
  TrendImpactPanel,
} from './TrendImpactPanel'

// The off-hours-tradeable risk set. Display order: equities, oil, gold, rates,
// crypto — same as the backend OVERNIGHT_LEAN_SYMBOLS.
const OVERNIGHT_CONFIG = {
  stocksSp: { name: 'S&P fut', color: 'var(--color-chart-blue)' },
  stocksNq: { name: 'Nasdaq fut', color: 'var(--color-chart-purple)' },
  oil: { name: 'Oil', color: 'var(--color-chart-orange)' },
  gold: { name: 'Gold', color: 'var(--color-chart-cyan)' },
  rates: { name: '10Y fut', color: 'var(--color-chart-green)' },
  crypto: { name: 'Bitcoin', color: 'var(--color-chart-red)' },
} as const

type OvernightKey = keyof typeof OVERNIGHT_CONFIG
const OVERNIGHT_KEYS = Object.keys(OVERNIGHT_CONFIG) as OvernightKey[]

function mapByDate(points: IndicatorDataPoint[] | undefined) {
  return new Map((points ?? []).map((point) => [point.date, point]))
}

function formatPct(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '-'
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

function directionTitle(lean: OvernightLean): string {
  if (lean.session === 'weekend') return 'Weekend — crypto only'
  switch (lean.direction) {
    case 'risk_off':
      return 'Leaning risk-off'
    case 'risk_on':
      return 'Leaning risk-on'
    case 'neutral':
      return 'Mixed / quiet'
    default:
      return 'Overnight read unavailable'
  }
}

function directionTone(direction: string): ImpactTone {
  if (direction === 'risk_off') return 'warning'
  if (direction === 'risk_on') return 'positive'
  return 'neutral'
}

function buildOvernightImpact(lean: OvernightLean | null): {
  tone: ImpactTone
  title: string
  summary: string
  metrics: ImpactMetric[]
  footer: string
} {
  if (!lean || !lean.applies) {
    return {
      tone: 'neutral',
      title: 'Live during market hours',
      summary:
        'Futures are the live tape while U.S. markets are open. The overnight lean returns after the close, when these instruments become the forward read.',
      metrics: [],
      footer: 'Returns at the close',
    }
  }

  const oil = lean.signals.find((s) => s.key === 'oil')
  const gold = lean.signals.find((s) => s.key === 'gold')

  return {
    tone: directionTone(lean.direction),
    title: directionTitle(lean),
    summary: lean.headline,
    metrics: [
      {
        label: 'Direction',
        value: directionTitle(lean),
        tone: directionTone(lean.direction),
      },
      {
        label: 'Agreement',
        value:
          lean.liveCount > 0 ? `${lean.confidence} of ${lean.liveCount}` : '—',
        detail: 'live signals aligned',
      },
      {
        label: 'Oil (WTI)',
        value: oil?.live ? formatPct(oil.changePct) : 'closed',
        detail: oil?.note ? 'geopolitical watch' : undefined,
        tone: oil?.note ? 'warning' : 'neutral',
      },
      {
        label: 'Caution',
        value: lean.droveCaution ? '↑ lifting' : 'context',
        detail: gold?.live ? `gold ${formatPct(gold.changePct)}` : undefined,
        tone: lean.droveCaution ? 'warning' : 'neutral',
      },
    ],
    footer: `${lean.sessionLabel}`,
  }
}

export function OvernightLeanChart() {
  const [timeframe, setTimeframe] = useState<Timeframe>(
    DEFAULT_MARKET_TIMEFRAME,
  )
  const [highlighted, setHighlighted] = useState<OvernightKey | null>(null)
  const [impactCollapsed, setImpactCollapsed] = useState(false)
  const days = timeframeToDays(timeframe)

  const { data, isLoading, error } = useOvernightHistory(days)
  const { data: conditions } = useMacroConditions()
  const lean = conditions?.overnightLean ?? null

  const chartData = useMemo(() => {
    if (!data) return []
    const maps = {
      stocksSp: mapByDate(data.stocksSp),
      stocksNq: mapByDate(data.stocksNq),
      oil: mapByDate(data.oil),
      gold: mapByDate(data.gold),
      rates: mapByDate(data.rates),
      crypto: mapByDate(data.crypto),
    }
    const dates = Array.from(
      new Set(
        OVERNIGHT_KEYS.flatMap((key) => (data[key] ?? []).map((p) => p.date)),
      ),
    ).sort()

    return dates.map((date) => {
      const row: Record<string, number | string | null> = { date }
      for (const key of OVERNIGHT_KEYS) {
        const point = maps[key].get(date)
        row[key] = point?.pctChange ?? null
        row[`${key}Value`] = point?.close ?? null
      }
      return row
    })
  }, [data])

  const currentValues = useMemo(() => {
    if (!data) return null
    const last = (arr: IndicatorDataPoint[] | undefined) =>
      arr && arr.length > 0 ? arr[arr.length - 1] : null
    return Object.fromEntries(
      OVERNIGHT_KEYS.map((key) => [key, last(data[key])]),
    ) as Record<OvernightKey, IndicatorDataPoint | null>
  }, [data])

  const formatXAxis = (date: string) => formatChartDate(date, days)
  const impact = buildOvernightImpact(lean)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    )
  }

  if (error || !data || chartData.length === 0) {
    return (
      <MarketPanelMessage
        message="Overnight instrument history is not available yet."
        className="min-h-48"
      />
    )
  }

  const formatTooltip = (
    value: number | undefined,
    name: string | undefined,
    props: { payload?: Record<string, number | null> },
  ): [string, string] => {
    if (!name) return ['', '']
    const config = OVERNIGHT_CONFIG[name as OvernightKey]
    const actualValue = props.payload?.[`${name}Value`]
    const numValue = value ?? 0
    const closeText =
      actualValue != null
        ? actualValue.toLocaleString(undefined, { maximumFractionDigits: 2 })
        : ''
    return [
      `${closeText} (${numValue >= 0 ? '+' : ''}${numValue.toFixed(1)}%)`,
      config?.name || name,
    ]
  }

  return (
    <TrendImpactPanel
      title="Overnight Lean"
      subtitle={`Forward off-hours read · ${timeframe} change window`}
      controls={<TimeframeSelector value={timeframe} onChange={setTimeframe} />}
      collapsed={impactCollapsed}
      chart={
        <div className="space-y-2">
          <div className="h-44">
            <ResponsiveContainer width="100%" height={176}>
              <LineChart
                data={chartData}
                margin={{ top: 5, right: 5, left: -20, bottom: 5 }}
              >
                <XAxis
                  dataKey="date"
                  tickFormatter={formatXAxis}
                  tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                  axisLine={{ stroke: 'var(--color-border)' }}
                  tickLine={false}
                  interval="preserveStartEnd"
                  minTickGap={36}
                />
                <YAxis
                  tickFormatter={(v) => `${v}%`}
                  tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                  axisLine={false}
                  tickLine={false}
                  width={40}
                />
                <ReferenceLine
                  y={0}
                  stroke="var(--color-border)"
                  strokeDasharray="3 3"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  // eslint-disable-next-line @typescript-eslint/no-explicit-any
                  formatter={formatTooltip as any}
                  labelFormatter={(label) =>
                    new Date(`${label}T12:00:00`).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })
                  }
                />
                {OVERNIGHT_KEYS.map((key) => (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={OVERNIGHT_CONFIG[key].color}
                    strokeWidth={highlighted === key ? 3 : 1.5}
                    dot={false}
                    opacity={
                      highlighted === null || highlighted === key ? 1 : 0.2
                    }
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
            {OVERNIGHT_KEYS.map((key) => {
              const config = OVERNIGHT_CONFIG[key]
              const pct = currentValues?.[key]?.pctChange ?? 0
              return (
                <button
                  key={key}
                  type="button"
                  aria-pressed={highlighted === key}
                  onClick={() =>
                    setHighlighted(highlighted === key ? null : key)
                  }
                  className={cn(
                    'flex items-center gap-1 rounded-md px-1.5 py-0.5 transition-all hover:bg-surface-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus',
                    highlighted !== null && highlighted !== key && 'opacity-40',
                  )}
                >
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: config.color }}
                  />
                  <span className="text-text-muted">
                    {config.name}{' '}
                    <span className={pct >= 0 ? 'text-gain' : 'text-loss'}>
                      {pct >= 0 ? '+' : ''}
                      {pct.toFixed(1)}%
                    </span>
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      }
      impact={
        <ImpactCard
          eyebrow="Impact"
          title={impact.title}
          summary={impact.summary}
          tone={impact.tone}
          metrics={impact.metrics}
          collapsed={impactCollapsed}
          onToggle={() => setImpactCollapsed((value) => !value)}
          footer={impact.footer}
        />
      }
    />
  )
}
