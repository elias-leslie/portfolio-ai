'use client'

import { Loader2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { SectionCard } from '@/components/shared/SectionCard'
import { useMacroBacktest } from '@/lib/hooks/useSignals'
import { cn } from '@/lib/utils'

const TIMEFRAMES = [
  { label: '6M', days: 183 },
  { label: '1Y', days: 365 },
  { label: '2Y', days: 730 },
] as const

const ZONE_META: Record<
  string,
  { label: string; className: string; color: string }
> = {
  FULL_DEPLOY: {
    label: 'Full deploy',
    className: 'border-success/40 bg-success/15 text-success',
    color: 'var(--color-success)',
  },
  REDUCED: {
    label: 'Reduced',
    className: 'border-warning/40 bg-warning/15 text-warning',
    color: 'var(--color-warning)',
  },
  DEFENSIVE: {
    label: 'Defensive',
    className: 'border-danger/40 bg-danger/15 text-danger',
    color: 'var(--color-danger)',
  },
}

interface GateChartPoint {
  date: string
  score: number
  zone: string
  coverage: number
}

function toInputDate(date: Date): string {
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

function formatDateLabel(value: string): string {
  return new Date(`${value}T12:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatShortDate(value: string): string {
  return new Date(`${value}T12:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    year: '2-digit',
  })
}

function zoneLabel(zone: string): string {
  return ZONE_META[zone]?.label ?? zone.replaceAll('_', ' ').toLowerCase()
}

function GateTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ payload: GateChartPoint }>
  label?: string | number
}) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  const meta = ZONE_META[point.zone]

  return (
    <div className="rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-lg">
      <div className="font-medium text-text">
        {formatDateLabel(String(label))}
      </div>
      <div className="mt-1 font-mono tabular-nums text-text">
        Score {point.score.toFixed(1)}
      </div>
      <div className="mt-1 flex items-center gap-2 text-text-muted">
        <span
          className="h-2 w-2 rounded-full"
          style={{ backgroundColor: meta?.color ?? 'var(--color-primary)' }}
        />
        {zoneLabel(point.zone)} · coverage {(point.coverage * 100).toFixed(0)}%
      </div>
    </div>
  )
}

function MetricTile({
  label,
  value,
  detail,
  tone = 'default',
}: {
  label: string
  value: string
  detail: string
  tone?: 'default' | 'success' | 'warning' | 'danger'
}) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border-subtle bg-bg/40 px-4 py-3',
        tone === 'success' && 'border-success/30 bg-success/5',
        tone === 'warning' && 'border-warning/30 bg-warning/5',
        tone === 'danger' && 'border-danger/30 bg-danger/5',
      )}
    >
      <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
        {label}
      </div>
      <div className="mt-1 font-mono text-lg tabular-nums text-text">
        {value}
      </div>
      <div className="mt-1 text-xs text-text-muted">{detail}</div>
    </div>
  )
}

export function MacroGateReplayPanel() {
  const [timeframeDays, setTimeframeDays] = useState(730)
  const range = useMemo(() => {
    const end = new Date()
    const start = new Date(end)
    start.setDate(start.getDate() - timeframeDays)
    return { start: toInputDate(start), end: toInputDate(end) }
  }, [timeframeDays])
  const { data, isLoading, error } = useMacroBacktest(range)

  const chartData = useMemo<GateChartPoint[]>(
    () =>
      (data?.rows ?? []).map((row) => ({
        date: row.snapshotDate,
        score: row.deploymentScore,
        zone: row.zone,
        coverage: row.coverage,
      })),
    [data?.rows],
  )

  const summary = useMemo(() => {
    if (!chartData.length) return null
    const latest = chartData[chartData.length - 1]
    const first = chartData[0]
    const avgScore =
      chartData.reduce((sum, row) => sum + row.score, 0) / chartData.length
    const avgCoverage =
      chartData.reduce((sum, row) => sum + row.coverage, 0) / chartData.length
    const zoneCounts = chartData.reduce<Record<string, number>>(
      (counts, row) => {
        counts[row.zone] = (counts[row.zone] ?? 0) + 1
        return counts
      },
      {},
    )
    return {
      latest,
      first,
      avgScore,
      avgCoverage,
      zoneCounts,
      scoreChange: latest.score - first.score,
    }
  }, [chartData])

  return (
    <SectionCard
      variant="surface"
      padding="md"
      title="Gate replay"
      description={
        data
          ? `${data.start} to ${data.end} · ${chartData.length} snapshots`
          : 'Historical deployment score replay.'
      }
      actions={
        <div className="flex rounded-xl border border-border-subtle bg-bg/40 p-1">
          {TIMEFRAMES.map((timeframe) => (
            <button
              key={timeframe.label}
              type="button"
              onClick={() => setTimeframeDays(timeframe.days)}
              className={cn(
                'rounded-lg px-3 py-1.5 text-xs font-semibold text-text-muted transition-colors hover:text-text',
                timeframeDays === timeframe.days &&
                  'bg-primary/20 text-primary shadow-sm',
              )}
            >
              {timeframe.label}
            </button>
          ))}
        </div>
      }
    >
      {error ? (
        <div className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
          {error instanceof Error
            ? error.message
            : 'Failed to load gate replay.'}
        </div>
      ) : isLoading ? (
        <div className="flex min-h-72 items-center justify-center text-sm text-text-muted">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Loading gate replay...
        </div>
      ) : chartData.length === 0 ? (
        <div className="rounded-xl border border-border-subtle bg-bg/40 px-4 py-8 text-center text-sm text-text-muted">
          No replay rows are available for this window.
        </div>
      ) : (
        <div className="space-y-5">
          {summary ? (
            <div className="grid gap-3 md:grid-cols-4">
              <MetricTile
                label="Latest zone"
                value={zoneLabel(summary.latest.zone)}
                detail={`${summary.latest.date} · ${summary.latest.score.toFixed(1)}`}
                tone={
                  summary.latest.zone === 'FULL_DEPLOY'
                    ? 'success'
                    : summary.latest.zone === 'REDUCED'
                      ? 'warning'
                      : 'danger'
                }
              />
              <MetricTile
                label="Avg score"
                value={summary.avgScore.toFixed(1)}
                detail={`${summary.scoreChange >= 0 ? '+' : ''}${summary.scoreChange.toFixed(1)} over window`}
              />
              <MetricTile
                label="Coverage"
                value={`${(summary.avgCoverage * 100).toFixed(0)}%`}
                detail="Average scored component weight"
              />
              <MetricTile
                label="Rows"
                value={chartData.length.toLocaleString()}
                detail={`${formatDateLabel(summary.first.date)} start`}
              />
            </div>
          ) : null}

          <div className="h-72">
            <ResponsiveContainer
              width="100%"
              height="100%"
              minWidth={0}
              minHeight={288}
            >
              <LineChart
                data={chartData}
                margin={{ top: 8, right: 12, left: -18, bottom: 0 }}
              >
                <CartesianGrid
                  vertical={false}
                  stroke="var(--color-border)"
                  strokeOpacity={0.35}
                />
                <ReferenceArea
                  y1={70}
                  y2={100}
                  fill="var(--color-success)"
                  fillOpacity={0.08}
                />
                <ReferenceArea
                  y1={40}
                  y2={70}
                  fill="var(--color-warning)"
                  fillOpacity={0.08}
                />
                <ReferenceArea
                  y1={0}
                  y2={40}
                  fill="var(--color-danger)"
                  fillOpacity={0.08}
                />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatShortDate}
                  tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                  axisLine={{ stroke: 'var(--color-border)' }}
                  tickLine={false}
                  interval="preserveStartEnd"
                  minTickGap={48}
                />
                <YAxis
                  domain={[0, 100]}
                  ticks={[0, 40, 70, 100]}
                  tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                  axisLine={false}
                  tickLine={false}
                  width={44}
                />
                <ReferenceLine
                  y={70}
                  stroke="var(--color-success)"
                  strokeDasharray="4 4"
                  strokeOpacity={0.8}
                />
                <ReferenceLine
                  y={40}
                  stroke="var(--color-warning)"
                  strokeDasharray="4 4"
                  strokeOpacity={0.8}
                />
                <Tooltip content={<GateTooltip />} />
                <Line
                  type="monotone"
                  dataKey="score"
                  stroke="var(--color-primary)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="flex flex-wrap gap-2">
            {Object.entries(summary?.zoneCounts ?? {}).map(([zone, count]) => (
              <span
                key={zone}
                className={cn(
                  'inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]',
                  ZONE_META[zone]?.className ??
                    'border-border-subtle bg-bg/50 text-text-muted',
                )}
              >
                {zoneLabel(zone)} {count}
              </span>
            ))}
            {Object.entries(data?.sanity ?? {}).map(([name, result]) => (
              <span
                key={name}
                className={cn(
                  'inline-flex items-center rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]',
                  result === 'pass'
                    ? 'border-success/40 bg-success/10 text-success'
                    : result === 'fail'
                      ? 'border-danger/40 bg-danger/10 text-danger'
                      : 'border-border-subtle bg-bg/50 text-text-muted',
                )}
              >
                {name.replaceAll('_', ' ')} {result}
              </span>
            ))}
          </div>
        </div>
      )}
    </SectionCard>
  )
}
