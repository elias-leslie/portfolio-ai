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
import type { SectorHistoryResponse } from '@/lib/api/market'
import { useMarketStatus } from '@/lib/hooks/useMarketIntelligence'
import { checkDataFreshness, cn, formatDate } from '@/lib/utils'
import { MarketPanelMessage } from './MarketPanelMessage'
import { SECTOR_COLORS } from './sector-colors'
import {
  formatChartDate,
  type Timeframe,
  TimeframeSelector,
  timeframeToDays,
} from './TimeframeSelector'

interface SectorPerformanceChartProps {
  timeframe: Timeframe
  onTimeframeChange: (timeframe: Timeframe) => void
  data?: SectorHistoryResponse
  isLoading?: boolean
  error?: Error | null
}

function sectorPointsByDate(
  sectors: SectorHistoryResponse['sectors'],
): Map<string, Map<string, { close: number; pctChange: number }>> {
  const maps = new Map<
    string,
    Map<string, { close: number; pctChange: number }>
  >()
  sectors.forEach((sector) => {
    maps.set(
      sector.symbol,
      new Map(
        sector.data.map((point) => [
          point.date,
          { close: point.close, pctChange: point.pctChange },
        ]),
      ),
    )
  })
  return maps
}

export function SectorPerformanceChart({
  timeframe,
  onTimeframeChange,
  data,
  isLoading = false,
  error = null,
}: SectorPerformanceChartProps) {
  const [highlightedSector, setHighlightedSector] = useState<string | null>(
    null,
  )
  const { data: marketStatus } = useMarketStatus()
  const days = timeframeToDays(timeframe)

  // Transform data for Recharts
  // Include both percentage change (for charting) and actual close price (for tooltips)
  const chartData = useMemo(() => {
    if (!data?.sectors?.length) return []

    const pointsBySector = sectorPointsByDate(data.sectors)
    const dates = Array.from(
      new Set(
        data.sectors.flatMap((sector) =>
          sector.data.map((point) => point.date),
        ),
      ),
    ).sort()

    return dates.map((date) => {
      const entry: Record<string, number | string | null> = { date }
      data.sectors.forEach((sector) => {
        const point = pointsBySector.get(sector.symbol)?.get(date)
        if (point) {
          entry[sector.symbol] = point.pctChange
          entry[`${sector.symbol}_price`] = point.close
        } else {
          entry[sector.symbol] = null
          entry[`${sector.symbol}_price`] = null
        }
      })
      return entry
    })
  }, [data])

  const formatXAxis = (date: string) => formatChartDate(date, days)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    )
  }

  if (error) {
    return (
      <MarketPanelMessage
        message="Unable to load sector performance right now."
        className="min-h-64"
      />
    )
  }

  if (!data?.sectors?.length || chartData.length === 0) {
    return (
      <MarketPanelMessage
        message="Sector performance history is not available yet."
        className="min-h-64"
      />
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-display italic text-lg tracking-tight text-text">
            Sector Trends
          </h3>
          <p className="mt-1 text-[10px] uppercase tracking-[0.16em] text-text-muted">
            Current/latest values · {timeframe} relative-performance window
          </p>
        </div>
        <TimeframeSelector value={timeframe} onChange={onTimeframeChange} />
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
              interval="preserveStartEnd"
              minTickGap={36}
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
              formatter={
                ((
                  value: number | undefined,
                  name: string | undefined,
                  props: { payload?: Record<string, number | null> },
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
                }) as any
              }
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
                highlightedSector !== null &&
                  highlightedSector !== sector.symbol &&
                  'opacity-40',
              )}
            >
              <span
                className="font-medium"
                style={{
                  color: SECTOR_COLORS[sector.symbol] || 'var(--color-neutral)',
                }}
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
