'use client'

import { Loader2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  useIndicatorHistory,
  useMarketStatus,
} from '@/lib/hooks/useMarketIntelligence'
import { checkDataFreshness, formatDate } from '@/lib/utils'
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

// Calendar-day lead so the 200-trading-day average is fully formed at the
// left edge of the display window (~290 calendar days ≈ 200 trading days).
const MA_LEAD_CALENDAR_DAYS = 320
const MAX_HISTORY_DAYS = 1825

const SERIES = {
  close: { name: 'S&P 500', color: 'var(--color-chart-blue)' },
  ma50: { name: '50-day avg', color: 'var(--color-chart-orange)' },
  ma200: { name: '200-day avg', color: 'var(--color-chart-red)' },
} as const

type SeriesKey = keyof typeof SERIES

interface TrendPoint {
  date: string
  close: number | null
  ma50: number | null
  ma200: number | null
}

function movingAverage(values: number[], index: number, window: number) {
  if (index + 1 < window) return null
  let sum = 0
  for (let i = index - window + 1; i <= index; i += 1) sum += values[i]
  return sum / window
}

function buildTrendImpact(latest: TrendPoint | null): {
  tone: ImpactTone
  title: string
  summary: string
  metrics: ImpactMetric[]
} {
  if (!latest?.close || !latest.ma200 || !latest.ma50) {
    return {
      tone: 'neutral',
      title: 'Trend read unavailable',
      summary:
        'Not enough S&P 500 history to compute the 50- and 200-day averages.',
      metrics: [],
    }
  }
  const aboveBoth = latest.close > latest.ma50 && latest.close > latest.ma200
  const below200 = latest.close < latest.ma200
  const tone: ImpactTone = aboveBoth
    ? 'positive'
    : below200
      ? 'negative'
      : 'neutral'
  const title = aboveBoth
    ? 'Uptrend intact'
    : below200
      ? 'Below the long-term trend'
      : 'Trend is being tested'
  const dist200 = ((latest.close - latest.ma200) / latest.ma200) * 100
  const dist50 = ((latest.close - latest.ma50) / latest.ma50) * 100
  const summary = aboveBoth
    ? 'Price is above both its 50- and 200-day averages — the simple trend read stays constructive.'
    : below200
      ? 'Price is under its 200-day average, the classic warning that the long-term trend has rolled over.'
      : 'Price is between its 50- and 200-day averages — the short-term trend is softening while the long-term trend holds.'
  const fmt = (value: number) =>
    value.toLocaleString(undefined, { maximumFractionDigits: 0 })
  const pct = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
  return {
    tone,
    title,
    summary,
    metrics: [
      { label: 'Close', value: fmt(latest.close), tone: 'neutral' },
      {
        label: 'vs 50-day',
        value: pct(dist50),
        detail: fmt(latest.ma50),
        tone: dist50 >= 0 ? 'positive' : 'warning',
      },
      {
        label: 'vs 200-day',
        value: pct(dist200),
        detail: fmt(latest.ma200),
        tone: dist200 >= 0 ? 'positive' : 'negative',
      },
    ],
  }
}

export function Sp500TrendChart() {
  const [timeframe, setTimeframe] = useState<Timeframe>(
    DEFAULT_MARKET_TIMEFRAME,
  )
  const [impactCollapsed, setImpactCollapsed] = useState(false)
  const windowDays = timeframeToDays(timeframe)
  const fetchDays = Math.min(
    windowDays + MA_LEAD_CALENDAR_DAYS,
    MAX_HISTORY_DAYS,
  )

  const { data, isLoading, error } = useIndicatorHistory(fetchDays)
  const { data: marketStatus } = useMarketStatus()

  const chartData = useMemo<TrendPoint[]>(() => {
    const points = data?.sp500 ?? []
    if (!points.length) return []
    const closes = points.map((point) => point.close)
    const full = points.map((point, index) => ({
      date: point.date,
      close: point.close,
      ma50: movingAverage(closes, index, 50),
      ma200: movingAverage(closes, index, 200),
    }))
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - windowDays)
    const cutoffKey = cutoff.toISOString().slice(0, 10)
    return full.filter((point) => point.date >= cutoffKey)
  }, [data, windowDays])

  const latest = chartData.length ? chartData[chartData.length - 1] : null
  const impact = buildTrendImpact(latest)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    )
  }

  if (error || !chartData.length) {
    return (
      <MarketPanelMessage
        message="S&P 500 trend history is not available right now."
        className="min-h-48"
      />
    )
  }

  return (
    <TrendImpactPanel
      title="S&P 500 Trend"
      subtitle={`Price vs 50- and 200-day averages · ${timeframe} window`}
      controls={<TimeframeSelector value={timeframe} onChange={setTimeframe} />}
      collapsed={impactCollapsed}
      chart={
        <div className="space-y-2">
          <div className="h-44">
            <ResponsiveContainer width="100%" height={176}>
              <LineChart
                data={chartData}
                margin={{ top: 5, right: 5, left: -8, bottom: 5 }}
              >
                <XAxis
                  dataKey="date"
                  tickFormatter={(date: string) =>
                    formatChartDate(date, windowDays)
                  }
                  tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                  axisLine={{ stroke: 'var(--color-border)' }}
                  tickLine={false}
                  interval="preserveStartEnd"
                  minTickGap={36}
                />
                <YAxis
                  domain={['auto', 'auto']}
                  tickFormatter={(value: number) =>
                    value.toLocaleString(undefined, {
                      maximumFractionDigits: 0,
                    })
                  }
                  tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                  axisLine={false}
                  tickLine={false}
                  width={52}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--color-surface)',
                    border: '1px solid var(--color-border)',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  formatter={(value, name) => [
                    typeof value === 'number'
                      ? value.toLocaleString(undefined, {
                          maximumFractionDigits: 0,
                        })
                      : '-',
                    SERIES[name as SeriesKey]?.name ?? String(name),
                  ]}
                  labelFormatter={(label) =>
                    new Date(`${label}T12:00:00`).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })
                  }
                />
                {(Object.keys(SERIES) as SeriesKey[]).map((key) => (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={SERIES[key].color}
                    strokeWidth={key === 'close' ? 2 : 1.25}
                    strokeDasharray={key === 'close' ? undefined : '5 3'}
                    dot={false}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
            {(Object.keys(SERIES) as SeriesKey[]).map((key) => (
              <span key={key} className="flex items-center gap-1">
                <span
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: SERIES[key].color }}
                />
                <span className="text-text-muted">{SERIES[key].name}</span>
              </span>
            ))}
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
          footer={
            latest
              ? (() => {
                  const freshness = checkDataFreshness(
                    latest.date,
                    marketStatus?.expectedDataDate,
                  )
                  return `Data as of ${formatDate(latest.date, false)} ${freshness.indicator}`
                })()
              : null
          }
        />
      }
    />
  )
}
