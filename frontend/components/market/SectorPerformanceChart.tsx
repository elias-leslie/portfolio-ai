'use client'

import { Loader2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { cn } from '@/lib/utils'
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
  useMarketStatus,
  useSectorHistory,
} from '@/lib/hooks/useMarketIntelligence'
import { checkDataFreshness, formatDate } from '@/lib/utils'
import { MarketPanelMessage } from './MarketPanelMessage'
import { SECTOR_COLORS } from './sector-colors'
import {
  calculateTickInterval,
  formatChartDate,
  type Timeframe,
  TimeframeSelector,
  timeframeToDays,
} from './TimeframeSelector'

export function SectorPerformanceChart() {
  const [timeframe, setTimeframe] = useState<Timeframe>('1Y')
  const [highlightedSector, setHighlightedSector] = useState<string | null>(
    null,
  )
  const days = timeframeToDays(timeframe)

  const { data, isLoading, error } = useSectorHistory(days)
  const { data: marketStatus } = useMarketStatus()

  // Transform data for Recharts
  // Include both percentage change (for charting) and actual close price (for tooltips)
  const chartData = useMemo(() => {
    if (!data?.sectors?.length) return []

    // Get all unique dates from the first sector (they should all have same dates)
    const firstSector = data.sectors[0]
    if (!firstSector?.data?.length) return []

    return firstSector.data.map((point, idx) => {
      const entry: Record<string, number | string> = { date: point.date }
      data.sectors.forEach((sector) => {
        if (sector.data[idx]) {
          entry[sector.symbol] = sector.data[idx].pctChange
          entry[`${sector.symbol}_price`] = sector.data[idx].close
        }
      })
      return entry
    })
  }, [data])

  // Use shared date formatting and tick calculation
  const formatXAxis = (date: string) => formatChartDate(date, days)
  const tickInterval = useMemo(
    () => calculateTickInterval(chartData.length),
    [chartData.length],
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    )
  }

  if (error) {
    return <MarketPanelMessage message="Unable to load sector performance right now." className="min-h-64" />
  }

  if (!data?.sectors?.length || chartData.length === 0) {
    return <MarketPanelMessage message="Sector performance history is not available yet." className="min-h-64" />
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-display italic text-lg tracking-tight text-text">Sector Performance</h3>
        <TimeframeSelector value={timeframe} onChange={setTimeframe} />
      </div>

      <div className="h-64">
        <ResponsiveContainer width="100%" height={256}>
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
              interval={tickInterval}
            />
            <YAxis
              tickFormatter={(v) => `${v}%`}
              tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
              axisLine={false}
              tickLine={false}
              width={45}
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
              formatter={((
                value: number | undefined,
                name: string | undefined,
                props: { payload?: Record<string, number> },
              ) => {
                if (!name) return ['', '']
                const sector = data.sectors.find((s) => s.symbol === name)
                const price = props.payload?.[`${name}_price`]
                const formattedPrice = price?.toFixed(2) ?? ''
                const numValue = value ?? 0
                return [
                  `$${formattedPrice} (${numValue >= 0 ? '+' : ''}${numValue.toFixed(1)}%)`,
                  sector?.name || name,
                ]
              }) as any}
              labelFormatter={(label) =>
                // Append T12:00:00 to avoid timezone shift
                new Date(`${label}T12:00:00`).toLocaleDateString('en-US', {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })
              }
            />
            {data.sectors.map((sector) => (
              <Line
                key={sector.symbol}
                type="monotone"
                dataKey={sector.symbol}
                stroke={SECTOR_COLORS[sector.symbol] || 'var(--color-neutral)'}
                strokeWidth={highlightedSector === sector.symbol ? 3 : 1.5}
                dot={false}
                opacity={
                  highlightedSector === null ||
                  highlightedSector === sector.symbol
                    ? 1
                    : 0.2
                }
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Interactive Legend */}
      <div className="flex items-center justify-between">
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
          {data.sectors.map((sector) => (
            <button
              key={sector.symbol}
              type="button"
              aria-pressed={highlightedSector === sector.symbol}
              onClick={() =>
                setHighlightedSector(
                  highlightedSector === sector.symbol ? null : sector.symbol,
                )
              }
              className={cn(
                'rounded-md px-1.5 py-0.5 transition-all hover:bg-surface-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus',
                highlightedSector !== null && highlightedSector !== sector.symbol && 'opacity-40',
              )}
            >
              <span
                className="font-medium"
                style={{ color: SECTOR_COLORS[sector.symbol] || 'var(--color-neutral)' }}
              >
                {sector.name}
              </span>
              <span>
                {' '}
                <span
                  className={sector.currentPct >= 0 ? 'text-gain' : 'text-loss'}
                >
                  {sector.currentPct >= 0 ? '+' : ''}
                  {sector.currentPct.toFixed(1)}%
                </span>
              </span>
            </button>
          ))}
        </div>
        {data.periodEnd &&
          (() => {
            const freshness = checkDataFreshness(
              data.periodEnd,
              marketStatus?.expectedDataDate,
            )
            return (
              <span
                className="text-[10px] text-text-muted whitespace-nowrap ml-2"
                title={freshness.tooltip}
              >
                Data as of {formatDate(data.periodEnd, false)}{' '}
                {freshness.indicator}
              </span>
            )
          })()}
      </div>
    </div>
  )
}
