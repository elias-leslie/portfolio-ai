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
import {
  ImpactCard,
  type ImpactMetric,
  type ImpactTone,
  TrendImpactPanel,
} from './TrendImpactPanel'

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

const CYCLICAL_SECTORS = new Set([
  'XLC',
  'XLY',
  'XLF',
  'XLI',
  'XLK',
  'XLE',
  'XLB',
])
const DEFENSIVE_SECTORS = new Set(['XLU', 'XLP', 'XLV', 'XLRE'])

function formatPct(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '-'
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`
}

function average(values: number[]) {
  if (values.length === 0) return null
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function sectorList(sectors: SectorHistoryResponse['sectors']) {
  return sectors
    .slice(0, 3)
    .map((sector) => `${sector.name} ${formatPct(sector.currentPct)}`)
    .join(' / ')
}

function buildSectorImpact(sectors: SectorHistoryResponse['sectors']): {
  tone: ImpactTone
  title: string
  summary: string
  metrics: ImpactMetric[]
} {
  if (sectors.length === 0) {
    return {
      tone: 'neutral',
      title: 'Sector leadership unavailable',
      summary:
        'Sector history is not available, so leadership quality cannot be evaluated.',
      metrics: [],
    }
  }

  const sorted = [...sectors].sort((a, b) => b.currentPct - a.currentPct)
  const topSector = sorted[0]
  const bottomSector = sorted.at(-1)
  const positiveCount = sectors.filter((sector) => sector.currentPct > 0).length
  const breadthPct = (positiveCount / sectors.length) * 100
  const cyclicalAvg = average(
    sectors
      .filter((sector) => CYCLICAL_SECTORS.has(sector.symbol))
      .map((sector) => sector.currentPct),
  )
  const defensiveAvg = average(
    sectors
      .filter((sector) => DEFENSIVE_SECTORS.has(sector.symbol))
      .map((sector) => sector.currentPct),
  )
  const tilt =
    cyclicalAvg != null && defensiveAvg != null
      ? cyclicalAvg - defensiveAvg
      : null
  const tone: ImpactTone =
    breadthPct >= 65 && (tilt ?? 0) >= 0
      ? 'positive'
      : breadthPct < 40
        ? 'negative'
        : 'neutral'
  const title =
    breadthPct >= 65 && (tilt ?? 0) >= 0
      ? 'Leadership is broad/risk-on'
      : breadthPct < 40
        ? 'Leadership is narrow'
        : 'Leadership is mixed'
  const summary = `Sector breadth is ${positiveCount}/${sectors.length} positive. ${tilt == null ? 'Cyclical/defensive tilt is unavailable.' : `Cyclicals are ${formatPct(tilt)} versus defensives.`}`

  return {
    tone,
    title,
    summary,
    metrics: [
      {
        label: 'Leading',
        value: topSector?.name ?? '-',
        detail: sectorList(sorted),
        tone: (topSector?.currentPct ?? 0) >= 0 ? 'positive' : 'negative',
      },
      {
        label: 'Lagging',
        value: bottomSector?.name ?? '-',
        detail: sectorList(sorted.slice(-3).reverse()),
        tone: (bottomSector?.currentPct ?? 0) >= 0 ? 'neutral' : 'negative',
      },
      {
        label: 'Breadth',
        value: `${positiveCount}/${sectors.length}`,
        detail: `${breadthPct.toFixed(0)}% positive`,
        tone:
          breadthPct >= 65
            ? 'positive'
            : breadthPct < 40
              ? 'negative'
              : 'neutral',
      },
      {
        label: 'Tilt',
        value: tilt == null ? '-' : formatPct(tilt),
        detail: 'cyclical minus defensive',
        tone: tilt == null ? 'neutral' : tilt >= 0 ? 'positive' : 'warning',
      },
    ],
  }
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
  const [impactCollapsed, setImpactCollapsed] = useState(false)
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
  const sectorImpact = buildSectorImpact(data?.sectors ?? [])

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
    <TrendImpactPanel
      title="Sector Trends"
      subtitle={`Current/latest values · ${timeframe} relative-performance window`}
      controls={
        <TimeframeSelector value={timeframe} onChange={onTimeframeChange} />
      }
      collapsed={impactCollapsed}
      chart={
        <div className="space-y-2">
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
                    stroke={
                      SECTOR_COLORS[sector.symbol] || 'var(--color-neutral)'
                    }
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
                    color:
                      SECTOR_COLORS[sector.symbol] || 'var(--color-neutral)',
                  }}
                >
                  {sector.name}
                </span>
                <span>
                  {' '}
                  <span
                    className={
                      sector.currentPct >= 0 ? 'text-gain' : 'text-loss'
                    }
                  >
                    {sector.currentPct >= 0 ? '+' : ''}
                    {sector.currentPct.toFixed(1)}%
                  </span>
                </span>
              </button>
            ))}
          </div>
        </div>
      }
      impact={
        <ImpactCard
          eyebrow="Impact"
          title={sectorImpact.title}
          summary={sectorImpact.summary}
          tone={sectorImpact.tone}
          metrics={sectorImpact.metrics}
          collapsed={impactCollapsed}
          onToggle={() => setImpactCollapsed((value) => !value)}
          footer={
            data.periodEnd
              ? (() => {
                  const freshness = checkDataFreshness(
                    data.periodEnd,
                    marketStatus?.expectedDataDate,
                  )
                  return `Data as of ${formatDate(data.periodEnd, false)} ${freshness.indicator}`
                })()
              : null
          }
        />
      }
    />
  )
}
