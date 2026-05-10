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
import {
  useIndicatorHistory,
  useMarketStatus,
} from '@/lib/hooks/useMarketIntelligence'
import { checkDataFreshness, cn, formatDate } from '@/lib/utils'
import { MarketPanelMessage } from './MarketPanelMessage'
import {
  DEFAULT_MARKET_TIMEFRAME,
  formatChartDate,
  type Timeframe,
  TimeframeSelector,
  timeframeToDays,
} from './TimeframeSelector'

const INDICATOR_CONFIG = {
  sp500: { name: 'S&P 500', color: 'var(--color-chart-blue)' },
  vix: { name: 'VIX', color: 'var(--color-chart-red)' },
  tnx: { name: '10Y Yield', color: 'var(--color-chart-orange)' },
  dxy: { name: 'Dollar', color: 'var(--color-chart-green)' },
}

type IndicatorKey = keyof typeof INDICATOR_CONFIG
type IndicatorPoint = { date: string; close: number; pctChange: number }

function mapByDate(points: IndicatorPoint[] | undefined) {
  return new Map((points ?? []).map((point) => [point.date, point]))
}

export function IndicatorsTrendChart() {
  const [timeframe, setTimeframe] = useState<Timeframe>(
    DEFAULT_MARKET_TIMEFRAME,
  )
  const [highlighted, setHighlighted] = useState<IndicatorKey | null>(null)
  const days = timeframeToDays(timeframe)

  const { data, isLoading, error } = useIndicatorHistory(days)
  const { data: marketStatus } = useMarketStatus()

  // Transform data for Recharts - merge all indicators by date
  // Include both percentage change (for charting) and actual values (for tooltips)
  const chartData = useMemo(() => {
    if (!data?.sp500?.length) return []

    const maps = {
      sp500: mapByDate(data.sp500),
      vix: mapByDate(data.vix),
      tnx: mapByDate(data.tnx),
      dxy: mapByDate(data.dxy),
    }
    const dates = Array.from(
      new Set(
        [...data.sp500, ...data.vix, ...data.tnx, ...data.dxy].map(
          (point) => point.date,
        ),
      ),
    ).sort()

    return dates.map((date) => {
      const sp500 = maps.sp500.get(date)
      const vix = maps.vix.get(date)
      const tnx = maps.tnx.get(date)
      const dxy = maps.dxy.get(date)
      return {
        date,
        sp500: sp500?.pctChange ?? null,
        sp500Value: sp500?.close ?? null,
        vix: vix?.pctChange ?? null,
        vixValue: vix?.close ?? null,
        tnx: tnx?.pctChange ?? null,
        tnxValue: tnx?.close ?? null,
        dxy: dxy?.pctChange ?? null,
        dxyValue: dxy?.close ?? null,
      }
    })
  }, [data])

  // Get current values for summary
  const currentValues = useMemo(() => {
    if (!data?.sp500?.length) return null
    const last = (arr: { pctChange: number; close: number }[]) =>
      arr.length > 0 ? arr[arr.length - 1] : null
    return {
      sp500: last(data.sp500),
      vix: last(data.vix),
      tnx: last(data.tnx),
      dxy: last(data.dxy),
    }
  }, [data])

  const formatXAxis = (date: string) => formatChartDate(date, days)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    )
  }

  if (error) {
    return (
      <MarketPanelMessage
        message="Unable to load key indicator history right now."
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
    const config = INDICATOR_CONFIG[name as IndicatorKey]
    const actualValue = props.payload?.[`${name}Value`]
    let formattedValue = ''
    if (name === 'sp500') {
      formattedValue =
        actualValue?.toLocaleString(undefined, {
          maximumFractionDigits: 0,
        }) ?? ''
    } else if (name === 'tnx') {
      formattedValue = `${actualValue?.toFixed(2) ?? ''}%`
    } else {
      formattedValue = actualValue?.toFixed(2) ?? ''
    }
    const numValue = value ?? 0
    return [
      `${formattedValue} (${numValue >= 0 ? '+' : ''}${numValue.toFixed(1)}%)`,
      config?.name || name,
    ]
  }

  if (!data?.sp500?.length || chartData.length === 0) {
    return (
      <MarketPanelMessage
        message="Key indicator history is not available yet."
        className="min-h-48"
      />
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-display italic text-lg tracking-tight text-text">
            Market Benchmarks
          </h3>
          <p className="mt-1 text-[10px] uppercase tracking-[0.16em] text-text-muted">
            Current/latest values · {timeframe} change window
          </p>
        </div>
        <TimeframeSelector value={timeframe} onChange={setTimeframe} />
      </div>

      <div className="h-40">
        <ResponsiveContainer width="100%" height={160}>
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
                // Append T12:00:00 to avoid timezone shift
                new Date(`${label}T12:00:00`).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })
              }
            />
            {(Object.keys(INDICATOR_CONFIG) as IndicatorKey[]).map((key) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={INDICATOR_CONFIG[key].color}
                strokeWidth={highlighted === key ? 3 : 1.5}
                dot={false}
                opacity={highlighted === null || highlighted === key ? 1 : 0.2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Interactive legend with current values */}
      <div className="flex items-center justify-between">
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {(Object.keys(INDICATOR_CONFIG) as IndicatorKey[]).map((key) => {
            const config = INDICATOR_CONFIG[key]
            const current = currentValues?.[key]
            const pct = current?.pctChange ?? 0
            return (
              <button
                key={key}
                type="button"
                aria-pressed={highlighted === key}
                onClick={() => setHighlighted(highlighted === key ? null : key)}
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
        {chartData.length > 0 &&
          (() => {
            const dataDate = chartData[chartData.length - 1].date.split('T')[0]
            const freshness = checkDataFreshness(
              dataDate,
              marketStatus?.expectedDataDate,
            )
            return (
              <span
                className="text-[10px] text-text-muted"
                title={freshness.tooltip}
              >
                Data as of {formatDate(dataDate, false)} {freshness.indicator}
              </span>
            )
          })()}
      </div>
    </div>
  )
}
