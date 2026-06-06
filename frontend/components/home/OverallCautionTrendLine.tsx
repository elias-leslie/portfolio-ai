'use client'

import { Loader2 } from 'lucide-react'
import { useMemo } from 'react'
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { MacroConditionsHistoryPoint } from '@/lib/api/macro'
import { useMacroConditionsHistory } from '@/lib/hooks/useMacro'
import { cn } from '@/lib/utils'

const WINDOW_DAYS = 90

// Higher Overall Caution == more caution == redder. Mirrors the backend
// thresholds (selective 35, severe 65) so the band labels match the hero state.
function cautionToneClass(
  value: number | null | undefined,
  selective: number,
  severe: number,
): string {
  if (value == null) return 'text-text-muted'
  if (value >= severe) return 'text-loss'
  if (value >= selective) return 'text-warning'
  return 'text-gain'
}

function formatTick(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return ''
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    month: 'short',
    day: 'numeric',
  }).format(parsed)
}

function formatStamp(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(parsed)
}

interface CautionDotProps {
  cx?: number
  cy?: number
  payload?: { tapeAvailable?: boolean; tapeState?: string | null }
}

// Live points (tape included) are filled; held points (off-hours, carrying the
// last live tape) are half-filled; macro-only points (tape unavailable / market
// closed with nothing to hold) are hollow — so a weekend/after-hours dip can't
// be mistaken for a real intraday move, but a held tape still reads as "real".
function CautionDot({ cx, cy, payload }: CautionDotProps) {
  if (cx == null || cy == null) return null
  const state =
    payload?.tapeState ?? (payload?.tapeAvailable ? 'live' : 'unavailable')
  if (state === 'held') {
    const r = 2.6
    return (
      <g>
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="var(--color-surface)"
          stroke="var(--color-warning)"
          strokeWidth={1.2}
        />
        <path
          d={`M ${cx} ${cy - r} A ${r} ${r} 0 0 1 ${cx} ${cy + r} Z`}
          fill="var(--color-warning)"
        />
      </g>
    )
  }
  const live = state === 'live'
  return (
    <circle
      cx={cx}
      cy={cy}
      r={live ? 2.6 : 2.2}
      fill={live ? 'var(--color-warning)' : 'var(--color-surface)'}
      stroke="var(--color-warning)"
      strokeWidth={1.2}
    />
  )
}

export function OverallCautionTrendLine() {
  const { data, isLoading, error } = useMacroConditionsHistory(WINDOW_DAYS)
  const selective = data?.selectiveThreshold ?? 35
  const severe = data?.severeThreshold ?? 65

  const chartData = useMemo(
    () =>
      (data?.points ?? [])
        .filter((p: MacroConditionsHistoryPoint) => p.overallCaution != null)
        .map((p: MacroConditionsHistoryPoint) => ({
          recordedAt: p.recordedAt,
          caution: p.overallCaution,
          macroStress: p.macroStress,
          tapePressure: p.tapePressure,
          tapeAvailable: p.tapeAvailable,
          tapeState: p.tapeState,
        })),
    [data],
  )

  const latest = chartData.at(-1)
  const first = chartData[0]
  const delta =
    latest?.caution != null && first?.caution != null
      ? latest.caution - first.caution
      : null
  const anyLive = chartData.some((p) => p.tapeAvailable)

  return (
    <div className="rounded-2xl border border-border-subtle bg-bg/20 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
            Overall Caution Trend
          </p>
          <p className="mt-1 text-xs text-text-muted">
            The headline caution number over the last {WINDOW_DAYS} days —
            higher is more cautious.
          </p>
        </div>
        <div className="text-right">
          <span
            className={cn(
              'font-mono text-2xl font-semibold leading-none tabular-nums',
              cautionToneClass(latest?.caution, selective, severe),
            )}
          >
            {latest?.caution ?? '-'}
          </span>
          {delta != null ? (
            <p
              className={cn(
                'mt-0.5 font-mono text-[10px] uppercase tracking-[0.14em]',
                delta > 0
                  ? 'text-loss'
                  : delta < 0
                    ? 'text-gain'
                    : 'text-text-muted',
              )}
            >
              {delta > 0 ? '+' : ''}
              {delta} over {WINDOW_DAYS}d
            </p>
          ) : null}
        </div>
      </div>

      <div className="mt-3 h-40">
        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-text-muted" />
          </div>
        ) : error ? (
          <div className="flex h-full items-center justify-center text-xs text-text-muted">
            Unable to load caution history right now.
          </div>
        ) : chartData.length === 0 ? (
          <div className="flex h-full items-center justify-center text-xs text-text-muted">
            Caution history is still building — points appear as the number
            changes.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 6, right: 8, left: -22, bottom: 2 }}
            >
              <XAxis
                dataKey="recordedAt"
                tickFormatter={formatTick}
                tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                axisLine={{ stroke: 'var(--color-border)' }}
                tickLine={false}
                interval="preserveStartEnd"
                minTickGap={36}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
                axisLine={false}
                tickLine={false}
                width={34}
              />
              <ReferenceLine
                y={severe}
                stroke="var(--color-loss)"
                strokeDasharray="3 3"
                opacity={0.4}
                label={{
                  value: `Defensive ${severe}`,
                  position: 'insideTopRight',
                  fontSize: 9,
                  fill: 'var(--color-loss)',
                }}
              />
              <ReferenceLine
                y={selective}
                stroke="var(--color-warning)"
                strokeDasharray="3 3"
                opacity={0.4}
                label={{
                  value: `Selective ${selective}`,
                  position: 'insideBottomRight',
                  fontSize: 9,
                  fill: 'var(--color-warning)',
                }}
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
                  ((value: number | undefined, name: string | undefined) => {
                    const labels: Record<string, string> = {
                      caution: 'Overall Caution',
                      macroStress: 'Macro Stress',
                      tapePressure: 'Tape Pressure',
                    }
                    return [
                      value != null ? `${value}` : '—',
                      labels[name ?? ''] ?? name,
                    ]
                  }) as any
                }
                labelFormatter={(label) => formatStamp(String(label))}
              />
              <Line
                type="monotone"
                dataKey="caution"
                stroke="var(--color-warning)"
                strokeWidth={2}
                dot={<CautionDot />}
                connectNulls
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-text-muted">
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-warning" />
          Live (incl. tape)
        </span>
        <span className="flex items-center gap-1">
          <span
            className="h-2 w-2 rounded-full border border-warning"
            style={{
              background:
                'linear-gradient(90deg, var(--color-warning) 50%, var(--color-surface) 50%)',
            }}
          />
          Held (last live tape)
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full border border-warning bg-surface" />
          Macro-only (tape unavailable / market closed)
        </span>
        {!anyLive ? (
          <span className="text-text-muted/80">
            History so far is macro-only; live tape points start logging during
            market hours.
          </span>
        ) : null}
      </div>
    </div>
  )
}
