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
import type { MacroSnapshot } from '@/lib/api/macro'
import { useMacroHistory } from '@/lib/hooks/useMacro'
import { formatDate } from '@/lib/utils'
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

const DRIVER_CONFIG = {
  vix: { label: 'VIX', color: 'var(--color-chart-red)' },
  term: { label: 'Curve', color: 'var(--color-chart-orange)' },
  breadth: { label: 'Breadth', color: 'var(--color-chart-cyan)' },
  credit: { label: 'Credit', color: 'var(--color-chart-green)' },
  putcall: { label: 'Put/Call', color: 'var(--color-chart-purple)' },
  crowding: { label: 'Crowding', color: 'var(--color-chart-blue)' },
} as const

type DriverKey = keyof typeof DRIVER_CONFIG

function formatScore(value: number | null | undefined) {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toFixed(0)
    : '-'
}

function formatRawValue(key: DriverKey, snapshot?: MacroSnapshot) {
  if (!snapshot) return '-'
  switch (key) {
    case 'vix':
      return snapshot.raw.vixClose?.toFixed(2) ?? '-'
    case 'term':
      return snapshot.raw.termSpreadBps != null
        ? `${snapshot.raw.termSpreadBps.toFixed(0)} bps`
        : '-'
    case 'breadth':
      return snapshot.raw.breadthPct != null
        ? `${snapshot.raw.breadthPct.toFixed(1)}%`
        : '-'
    case 'credit':
      return snapshot.raw.hySpread != null
        ? `${snapshot.raw.hySpread.toFixed(2)}%`
        : '-'
    case 'putcall':
      return snapshot.raw.putCallRatio?.toFixed(2) ?? '-'
    case 'crowding':
      return snapshot.raw.factorCrowdingCorr?.toFixed(2) ?? '-'
    default:
      return '-'
  }
}

function scoreTone(value: number | null | undefined): ImpactTone {
  if (value == null) return 'negative'
  if (value >= 70) return 'positive'
  if (value >= 40) return 'neutral'
  return 'warning'
}

function buildDriverImpact(snapshots: MacroSnapshot[]): {
  tone: ImpactTone
  title: string
  summary: string
  metrics: ImpactMetric[]
  footer: string | null
} {
  const latest = snapshots.at(-1)
  if (!latest) {
    return {
      tone: 'neutral',
      title: 'Driver history unavailable',
      summary:
        'Macro driver history is not available yet, so Daily Brief has only the current score snapshot.',
      metrics: [],
      footer: null,
    }
  }

  const scored = (Object.keys(DRIVER_CONFIG) as DriverKey[])
    .map((key) => ({
      key,
      label: DRIVER_CONFIG[key].label,
      score: latest.components[key],
      quality: latest.componentQuality[key],
    }))
    .filter((row) => row.score != null)
  const weakest = [...scored].sort((a, b) => (a.score ?? 0) - (b.score ?? 0))[0]
  const strongest = [...scored].sort(
    (a, b) => (b.score ?? 0) - (a.score ?? 0),
  )[0]
  const first = snapshots[0]
  const scoreDelta =
    first?.deploymentScore != null
      ? latest.deploymentScore - first.deploymentScore
      : null
  const missing = (Object.keys(DRIVER_CONFIG) as DriverKey[]).filter(
    (key) => latest.components[key] == null,
  )
  const tone: ImpactTone =
    latest.coverage != null && latest.coverage < 1
      ? 'warning'
      : weakest?.score != null && weakest.score < 35
        ? 'warning'
        : latest.deploymentScore >= 70
          ? 'positive'
          : latest.deploymentScore < 40
            ? 'negative'
            : 'neutral'
  const title =
    missing.length > 0
      ? 'Regime drivers are incomplete'
      : weakest?.score != null && weakest.score < 35
        ? `${weakest.label} is the main drag`
        : latest.deploymentScore >= 70
          ? 'Drivers support risk'
          : latest.deploymentScore < 40
            ? 'Drivers are defensive'
            : 'Drivers are mixed'
  const deltaText =
    scoreDelta == null
      ? 'trend is still building'
      : `${scoreDelta >= 0 ? 'up' : 'down'} ${Math.abs(scoreDelta).toFixed(1)} pts over this window`

  return {
    tone,
    title,
    summary: `Regime score is ${latest.deploymentScore.toFixed(0)} and ${deltaText}. Strongest driver: ${strongest?.label ?? '-'}. Weakest driver: ${weakest?.label ?? '-'}.`,
    metrics: [
      {
        label: 'Weakest',
        value: weakest ? `${weakest.label} ${formatScore(weakest.score)}` : '-',
        detail: weakest ? formatRawValue(weakest.key, latest) : undefined,
        tone: scoreTone(weakest?.score),
      },
      {
        label: 'Strongest',
        value: strongest
          ? `${strongest.label} ${formatScore(strongest.score)}`
          : '-',
        detail: strongest ? formatRawValue(strongest.key, latest) : undefined,
        tone: scoreTone(strongest?.score),
      },
      {
        label: 'Coverage',
        value:
          latest.coverage != null
            ? `${Math.round(latest.coverage * 100)}%`
            : '-',
        detail:
          missing.length > 0 ? `Missing ${missing.join(', ')}` : 'all drivers',
        tone: missing.length > 0 ? 'warning' : 'positive',
      },
      {
        label: 'Score trend',
        value:
          scoreDelta == null
            ? '-'
            : `${scoreDelta >= 0 ? '+' : ''}${scoreDelta.toFixed(1)}`,
        detail: `${snapshots.length} snapshots`,
        tone:
          scoreDelta == null
            ? 'neutral'
            : scoreDelta >= 0
              ? 'positive'
              : 'warning',
      },
    ],
    footer: `Latest snapshot ${formatDate(latest.snapshotDate, false)} · zone ${latest.zone.replaceAll('_', ' ')}`,
  }
}

export function MacroRegimeDriversTrendChart() {
  const [timeframe, setTimeframe] = useState<Timeframe>(
    DEFAULT_MARKET_TIMEFRAME,
  )
  const [impactCollapsed, setImpactCollapsed] = useState(false)
  const days = timeframeToDays(timeframe)
  const { data, isLoading, error } = useMacroHistory(days)
  const snapshots = data?.snapshots ?? []

  const chartData = useMemo(
    () =>
      snapshots.map((snapshot) => ({
        date: snapshot.snapshotDate,
        score: snapshot.deploymentScore,
        vix: snapshot.components.vix,
        term: snapshot.components.term,
        breadth: snapshot.components.breadth,
        credit: snapshot.components.credit,
        putcall: snapshot.components.putcall,
        crowding: snapshot.components.crowding,
      })),
    [snapshots],
  )
  const driverImpact = buildDriverImpact(snapshots)
  const formatXAxis = (date: string) => formatChartDate(date, days)

  if (isLoading) {
    return (
      <div className="flex h-48 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-text-muted" />
      </div>
    )
  }

  if (error) {
    return (
      <MarketPanelMessage
        message="Unable to load regime driver history right now."
        className="min-h-48"
      />
    )
  }

  if (chartData.length === 0) {
    return (
      <MarketPanelMessage
        message="Regime driver history is not available yet."
        className="min-h-48"
      />
    )
  }

  return (
    <TrendImpactPanel
      title="Regime Drivers"
      subtitle={`Macro score inputs · ${timeframe} trend window`}
      controls={<TimeframeSelector value={timeframe} onChange={setTimeframe} />}
      collapsed={impactCollapsed}
      chart={
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
          {(Object.keys(DRIVER_CONFIG) as DriverKey[]).map((key) => {
            const latestSnapshot = snapshots.at(-1)
            const current = latestSnapshot?.components[key]
            return (
              <div
                key={key}
                className="rounded-lg border border-border-subtle bg-bg/25 px-2.5 pt-2 pb-1"
              >
                <div className="flex items-baseline justify-between">
                  <span className="flex items-center gap-1.5 text-[11px] text-text-muted">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: DRIVER_CONFIG[key].color }}
                    />
                    {DRIVER_CONFIG[key].label}
                  </span>
                  <span className="font-mono text-xs text-text">
                    {formatScore(current)}
                    <span className="ml-1 text-[10px] text-text-muted">
                      {formatRawValue(key, latestSnapshot)}
                    </span>
                  </span>
                </div>
                <div className="h-14">
                  <ResponsiveContainer width="100%" height={56}>
                    <LineChart
                      data={chartData}
                      margin={{ top: 6, right: 2, left: 2, bottom: 2 }}
                    >
                      <XAxis dataKey="date" hide />
                      <YAxis domain={[0, 100]} hide />
                      <ReferenceLine
                        y={70}
                        stroke="var(--color-gain)"
                        strokeDasharray="3 3"
                        opacity={0.3}
                      />
                      <ReferenceLine
                        y={40}
                        stroke="var(--color-warning)"
                        strokeDasharray="3 3"
                        opacity={0.3}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'var(--color-surface)',
                          border: '1px solid var(--color-border)',
                          borderRadius: '8px',
                          fontSize: '11px',
                          padding: '4px 8px',
                        }}
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        formatter={
                          ((value: number | undefined) => [
                            value != null ? value.toFixed(1) : '-',
                            DRIVER_CONFIG[key].label,
                          ]) as any
                        }
                        labelFormatter={(label) =>
                          new Date(`${label}T12:00:00`).toLocaleDateString(
                            'en-US',
                            { month: 'short', day: 'numeric' },
                          )
                        }
                      />
                      <Line
                        type="monotone"
                        dataKey={key}
                        stroke={DRIVER_CONFIG[key].color}
                        strokeWidth={1.5}
                        dot={false}
                        connectNulls
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-right text-[9px] text-text-muted">
                  {formatXAxis(chartData[0]?.date ?? '')} →{' '}
                  {formatXAxis(chartData[chartData.length - 1]?.date ?? '')}
                </p>
              </div>
            )
          })}
        </div>
      }
      impact={
        <ImpactCard
          eyebrow="Impact"
          title={driverImpact.title}
          summary={driverImpact.summary}
          tone={driverImpact.tone}
          metrics={driverImpact.metrics}
          collapsed={impactCollapsed}
          onToggle={() => setImpactCollapsed((value) => !value)}
          footer={driverImpact.footer}
        />
      }
    />
  )
}
