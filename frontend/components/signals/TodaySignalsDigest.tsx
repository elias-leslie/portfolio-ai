'use client'

import { ArrowRight } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import type { CommitteeRunListItem } from '@/lib/committee/api'
import { fetchCommitteeRuns } from '@/lib/committee/api'
import { useBlendedSignals } from '@/lib/hooks/useSignals'
import { useWatchlist } from '@/lib/hooks/useWatchlist'
import { cn } from '@/lib/utils'
import { DeterministicBadge, NonDeterministicBadge } from './badges'

function isToday(iso?: string | null): boolean {
  if (!iso) return false
  const d = new Date(iso)
  const now = new Date()
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  )
}

function ScannerTopColumn() {
  const { data, isLoading, error } = useBlendedSignals({ limit: 5 })
  const rows = data?.rows ?? []

  return (
    <div className="space-y-3 border-l-2 border-[#00f5ff]/30 pl-4">
      <div className="flex items-center justify-between">
        <h3 className="font-display italic text-sm tracking-tight text-text">
          Scanner top 5
        </h3>
        <DeterministicBadge label="DETERMINISTIC" className="text-[9px]" />
      </div>
      {error ? (
        <p className="text-xs text-danger">
          {error instanceof Error ? error.message : 'Scanner unavailable'}
        </p>
      ) : isLoading ? (
        <p className="text-xs text-text-muted">Loading scanner…</p>
      ) : rows.length === 0 ? (
        <p className="text-xs text-text-muted">
          No scanner candidates today (gate may be defensive).
        </p>
      ) : (
        <ul className="space-y-1.5">
          {rows.slice(0, 5).map((row) => (
            <li
              key={row.symbol}
              className="flex items-center justify-between rounded-lg border border-border-subtle bg-bg/40 px-3 py-2 text-sm"
            >
              <Link
                href={`/symbols/${row.symbol}`}
                className="font-mono font-semibold text-primary hover:underline"
              >
                {row.symbol}
              </Link>
              <div className="flex items-center gap-3 text-xs text-text-muted">
                <span className="font-mono tabular-nums">
                  #{row.blendedRank}
                </span>
                <span className="font-mono tabular-nums text-text">
                  {row.blendedScore.toFixed(1)}
                </span>
                {row.flagged ? (
                  <span
                    className={cn(
                      'rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em]',
                      row.deltaRank > 0
                        ? 'bg-success/20 text-success'
                        : 'bg-danger/20 text-danger',
                    )}
                    title={`${row.deltaRank > 0 ? 'Upgraded' : 'Downgraded'} ${Math.abs(row.deltaRank)} places vs. scanner-only rank`}
                  >
                    {row.deltaRank > 0 ? '▲' : '▼'} {Math.abs(row.deltaRank)}
                  </span>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
      <Link
        href="/portfolio?tab=signals"
        className="inline-flex items-center text-xs font-medium text-primary hover:underline"
      >
        Full scanner table
        <ArrowRight className="ml-1 h-3 w-3" />
      </Link>
    </div>
  )
}

function CommitteeTodayColumn() {
  const [runs, setRuns] = useState<CommitteeRunListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchCommitteeRuns(20)
      .then((res) => {
        if (cancelled) return
        const todays = res.runs.filter((r) =>
          isToday(r.completed_at ?? r.started_at),
        )
        setRuns(todays.slice(0, 3))
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message)
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="space-y-3 border-l-2 border-[#a855f7]/30 pl-4">
      <div className="flex items-center justify-between">
        <h3 className="font-display italic text-sm tracking-tight text-text">
          Committee verdicts today
        </h3>
        <NonDeterministicBadge />
      </div>
      {error ? (
        <p className="text-xs text-danger">{error}</p>
      ) : runs === null ? (
        <p className="text-xs text-text-muted">Loading verdicts…</p>
      ) : runs.length === 0 ? (
        <p className="text-xs text-text-muted">
          No committee runs completed yet today.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {runs.map((run) => (
            <li
              key={run.id}
              className="flex items-center justify-between rounded-lg border border-border-subtle bg-bg/40 px-3 py-2 text-sm"
            >
              <div className="flex items-center gap-2">
                <Link
                  href={`/portfolio/committee/${run.id}`}
                  className="font-mono font-semibold text-primary hover:underline"
                >
                  {run.symbol}
                </Link>
                <span className="text-xs text-text-muted">
                  {run.decision_action ?? run.status}
                </span>
              </div>
              {run.confidence != null ? (
                <span className="font-mono text-xs tabular-nums text-text-muted">
                  {(run.confidence * 100).toFixed(0)}%
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      <Link
        href="/portfolio?tab=committee"
        className="inline-flex items-center text-xs font-medium text-primary hover:underline"
      >
        Committee workspace
        <ArrowRight className="ml-1 h-3 w-3" />
      </Link>
    </div>
  )
}

function WatchlistAlertsColumn() {
  const { data, isLoading, error } = useWatchlist()

  const alerts = (data?.items ?? [])
    .filter((item) => (item.signalStrength ?? 0) >= 70)
    .sort((a, b) => (b.signalStrength ?? 0) - (a.signalStrength ?? 0))
    .slice(0, 3)

  return (
    <div className="space-y-3 border-l-2 border-[#00f5ff]/30 pl-4">
      <div className="flex items-center justify-between">
        <h3 className="font-display italic text-sm tracking-tight text-text">
          Watchlist alerts
        </h3>
      </div>
      {error ? (
        <p className="text-xs text-danger">
          {error instanceof Error ? error.message : 'Watchlist unavailable'}
        </p>
      ) : isLoading ? (
        <p className="text-xs text-text-muted">Loading watchlist…</p>
      ) : alerts.length === 0 ? (
        <p className="text-xs text-text-muted">No high-strength alerts.</p>
      ) : (
        <ul className="space-y-1.5">
          {alerts.map((item) => (
            <li
              key={item.id}
              className="flex items-center justify-between rounded-lg border border-border-subtle bg-bg/40 px-3 py-2 text-sm"
            >
              <Link
                href={`/symbols/${item.symbol}`}
                className="font-mono font-semibold text-primary hover:underline"
              >
                {item.symbol}
              </Link>
              <div className="flex items-center gap-2 text-xs text-text-muted">
                <span>{item.signalType ?? '—'}</span>
                <span className="font-mono tabular-nums text-text">
                  {item.signalStrength ?? '—'}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
      <Link
        href="/portfolio?tab=symbols"
        className="inline-flex items-center text-xs font-medium text-primary hover:underline"
      >
        Full watchlist
        <ArrowRight className="ml-1 h-3 w-3" />
      </Link>
    </div>
  )
}

export function TodaySignalsDigest() {
  return (
    <SectionCard variant="surface" title="Today's signals" padding="md">
      <div className="grid gap-5 md:grid-cols-3">
        <ScannerTopColumn />
        <CommitteeTodayColumn />
        <WatchlistAlertsColumn />
      </div>
    </SectionCard>
  )
}
