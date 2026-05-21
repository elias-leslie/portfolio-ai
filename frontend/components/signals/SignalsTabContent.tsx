'use client'

import { Clock3, Gauge, Shuffle, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import type { BlendedResponse, BlendedRow } from '@/lib/api/signals'
import { useBlendedSignals, useScannerLatest } from '@/lib/hooks/useSignals'
import { cn } from '@/lib/utils'
import { BlendWeightControl, loadStoredScannerPct } from './BlendWeightControl'
import { MacroGateReplayPanel } from './MacroGateReplayPanel'
import { ScannerTable } from './ScannerTable'

const SCORE_BUCKETS = [
  { label: '90-100', min: 90, max: 100 },
  { label: '80-89', min: 80, max: 89.999 },
  { label: '70-79', min: 70, max: 79.999 },
  { label: '60-69', min: 60, max: 69.999 },
  { label: '<60', min: Number.NEGATIVE_INFINITY, max: 59.999 },
]

function formatScore(value: number | null | undefined): string {
  return value == null ? '-' : value.toFixed(1)
}

function formatPct(value: number): string {
  return `${Math.round(value * 100)}%`
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '-'
  return new Date(`${value}T12:00:00`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function SummaryTile({
  icon: Icon,
  label,
  value,
  detail,
  className,
}: {
  icon: typeof Clock3
  label: string
  value: string
  detail: string
  className?: string
}) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border-subtle bg-bg/40 px-4 py-3',
        className,
      )}
    >
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="mt-2 font-mono text-lg tabular-nums text-text">
        {value}
      </div>
      <div className="mt-1 text-xs text-text-muted">{detail}</div>
    </div>
  )
}

function SignalRunSummary({
  data,
  isLoading,
  error,
}: {
  data: BlendedResponse | undefined
  isLoading: boolean
  error: unknown
}) {
  if (error) {
    return (
      <div className="rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
        {error instanceof Error ? error.message : 'Failed to load signal run.'}
      </div>
    )
  }

  if (isLoading || !data) {
    return (
      <div className="grid gap-3 md:grid-cols-4">
        {['Run', 'Coverage', 'Gate', 'Committee'].map((label) => (
          <div
            key={label}
            className="h-24 animate-pulse rounded-xl border border-border-subtle bg-surface/50"
          />
        ))}
      </div>
    )
  }

  const rows = data.rows
  const committeeRows = rows.filter((row) => row.committee)
  const flaggedRows = rows.filter((row) => row.flagged)
  const topRow = rows[0]
  const scoredRatio =
    data.run.universeSize > 0 ? data.run.scoredCount / data.run.universeSize : 0

  return (
    <div className="grid gap-3 md:grid-cols-4">
      <SummaryTile
        icon={Clock3}
        label="Run"
        value={formatDate(data.run.runDate)}
        detail={`${rows.length} blended rows loaded`}
      />
      <SummaryTile
        icon={Gauge}
        label="Coverage"
        value={`${data.run.scoredCount}/${data.run.universeSize}`}
        detail={`${formatPct(scoredRatio)} of universe scored`}
      />
      <SummaryTile
        icon={Sparkles}
        label="Top signal"
        value={topRow?.symbol ?? '-'}
        detail={`Blended score ${formatScore(topRow?.blendedScore)}`}
      />
      <SummaryTile
        icon={Shuffle}
        label="Committee impact"
        value={`${flaggedRows.length} flagged`}
        detail={`${committeeRows.length} verdicts in this run`}
      />
    </div>
  )
}

function SignalScoreDistribution({ rows }: { rows: BlendedRow[] }) {
  const buckets = useMemo(() => {
    const counts = SCORE_BUCKETS.map((bucket) => ({
      ...bucket,
      count: rows.filter(
        (row) =>
          row.blendedScore >= bucket.min && row.blendedScore <= bucket.max,
      ).length,
    }))
    const maxCount = Math.max(1, ...counts.map((bucket) => bucket.count))
    return counts.map((bucket) => ({
      ...bucket,
      pct: (bucket.count / maxCount) * 100,
    }))
  }, [rows])

  return (
    <SectionCard
      variant="surface"
      padding="md"
      title="Score distribution"
      description={`${rows.length} symbols by blended score`}
    >
      {rows.length === 0 ? (
        <p className="text-sm text-text-muted">No scores in this run.</p>
      ) : (
        <div className="space-y-3">
          {buckets.map((bucket) => (
            <div key={bucket.label} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="font-mono text-text-muted">
                  {bucket.label}
                </span>
                <span className="font-mono tabular-nums text-text">
                  {bucket.count}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-bg/70">
                <div
                  className="h-full rounded-full bg-primary/70"
                  style={{ width: `${bucket.pct}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  )
}

function CommitteeRankImpact({ rows }: { rows: BlendedRow[] }) {
  const movers = useMemo(
    () =>
      rows
        .filter((row) => row.flagged)
        .sort((a, b) => Math.abs(b.deltaRank) - Math.abs(a.deltaRank))
        .slice(0, 8),
    [rows],
  )

  return (
    <SectionCard
      variant="surface"
      padding="md"
      title="Rank impact"
      description="Largest committee moves versus scanner-only rank"
    >
      {movers.length === 0 ? (
        <p className="text-sm text-text-muted">
          No committee moves crossed the flag threshold.
        </p>
      ) : (
        <ul className="space-y-2">
          {movers.map((row) => (
            <li
              key={row.symbol}
              className="rounded-xl border border-border-subtle bg-bg/40 px-3 py-2"
            >
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-mono font-semibold text-primary">
                    {row.symbol}
                  </div>
                  <div className="mt-0.5 text-xs text-text-muted">
                    #{row.scannerRank} scanner to #{row.blendedRank} blended
                  </div>
                </div>
                <span
                  className={cn(
                    'rounded-full px-2 py-1 font-mono text-xs font-semibold tabular-nums',
                    row.deltaRank > 0
                      ? 'bg-success/15 text-success'
                      : 'bg-danger/15 text-danger',
                  )}
                >
                  {row.deltaRank > 0 ? '+' : ''}
                  {row.deltaRank}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  )
}

export function SignalsTabContent() {
  const [scannerPct, setScannerPct] = useState<number>(60)

  useEffect(() => {
    setScannerPct(loadStoredScannerPct())
  }, [])

  const weights = useMemo(() => {
    const s = scannerPct / 100
    return { weightScanner: s, weightCommittee: 1 - s }
  }, [scannerPct])

  const blended = useBlendedSignals({ limit: 100, ...weights })
  const scannerLatest = useScannerLatest(100)

  const factorPercentilesBySymbol = useMemo(() => {
    const out: Record<string, Record<string, number | null>> = {}
    for (const score of scannerLatest.data?.scores ?? []) {
      out[score.symbol] = score.percentiles
    }
    return out
  }, [scannerLatest.data])

  return (
    <div className="space-y-4">
      <SignalRunSummary
        data={blended.data}
        isLoading={blended.isLoading}
        error={blended.error}
      />

      <SectionCard
        variant="surface"
        padding="md"
        title="Blended scanner"
        description={
          blended.data
            ? `${blended.data.run.scoredCount} symbols ranked from run ${blended.data.run.runDate} · gate ${blended.data.run.gateZone}`
            : 'Blending the L2 scanner with the L3 committee verdict.'
        }
      >
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_18rem]">
          <div className="min-w-0">
            {blended.error ? (
              <div className="rounded-2xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
                {blended.error instanceof Error
                  ? blended.error.message
                  : 'Failed to load blended signals.'}
              </div>
            ) : blended.isLoading ? (
              <div className="rounded-2xl border border-border-subtle bg-surface/50 px-4 py-6 text-sm text-text-muted">
                Loading blended signals…
              </div>
            ) : (
              <ScannerTable
                rows={blended.data?.rows ?? []}
                factorPercentilesBySymbol={factorPercentilesBySymbol}
              />
            )}
          </div>
          <div>
            <BlendWeightControl value={scannerPct} onChange={setScannerPct} />
          </div>
        </div>
      </SectionCard>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <SignalScoreDistribution rows={blended.data?.rows ?? []} />
        <CommitteeRankImpact rows={blended.data?.rows ?? []} />
      </div>

      <MacroGateReplayPanel />
    </div>
  )
}
