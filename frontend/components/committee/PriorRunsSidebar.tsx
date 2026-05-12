'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import {
  type CommitteeRunListItem,
  fetchCommitteeRuns,
} from '@/lib/committee/api'
import { cn } from '@/lib/utils'

function timeAgo(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  const now = Date.now()
  const seconds = Math.floor((now - date.getTime()) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 48) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function actionTone(action: string | null): string {
  switch (action) {
    case 'buy':
    case 'add':
      return 'text-gain-strong border-gain/50'
    case 'sell':
    case 'trim':
      return 'text-loss-strong border-loss/50'
    case 'hold':
      return 'text-warning-strong border-warning/40'
    default:
      return 'text-text-muted border-border-subtle'
  }
}

function statusTone(status: string): string {
  switch (status) {
    case 'running':
    case 'pending':
      return 'text-primary border-primary/50'
    case 'complete':
      return 'text-gain-strong border-gain/50'
    case 'approved':
      return 'text-accent border-accent/40'
    case 'aborted':
      return 'text-loss-strong border-loss/50'
    case 'failed':
      return 'text-loss-strong border-loss/50'
    default:
      return 'text-text-muted border-border-subtle'
  }
}

export function PriorRunsSidebar() {
  const [runs, setRuns] = useState<CommitteeRunListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const data = await fetchCommitteeRuns(20)
        if (active) {
          setRuns(data.runs)
          setError(null)
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : 'Failed to load')
        }
      }
    }
    load()
    const interval = setInterval(load, 5000)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [])

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border-subtle px-3 py-2 text-[10px] uppercase tracking-[0.18em] text-text-muted/70">
        <span>Prior runs</span>
        {runs ? (
          <span className="font-mono text-text-muted">{runs.length}</span>
        ) : null}
      </div>
      <div className="max-h-[70vh] overflow-y-auto">
        {error ? (
          <p className="px-3 py-3 text-[12px] text-loss-strong">{error}</p>
        ) : runs === null ? (
          <p className="px-3 py-3 text-[12px] text-text-muted/60">Loading…</p>
        ) : runs.length === 0 ? (
          <p className="px-3 py-3 text-[12px] text-text-muted/60">
            No prior runs yet — start one above.
          </p>
        ) : (
          runs.map((run) => (
            <Link
              key={run.id}
              href={`/portfolio/committee/${run.id}`}
              className="block border-b border-border-subtle px-3 py-2.5 transition-colors hover:bg-surface-elev/60"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-mono text-sm font-bold text-text">
                  {run.symbol}
                </span>
                <span className="font-mono text-[10px] text-text-muted">
                  {timeAgo(run.started_at)}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <span
                  className={cn(
                    'rounded-md border bg-bg px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em]',
                    statusTone(run.status),
                  )}
                >
                  {run.status}
                </span>
                {run.decision_action ? (
                  <span
                    className={cn(
                      'rounded-md border bg-bg px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em]',
                      actionTone(run.decision_action),
                    )}
                  >
                    {run.decision_action}
                    {run.decision_pct_portfolio
                      ? ` ${(run.decision_pct_portfolio * 100).toFixed(1)}%`
                      : ''}
                  </span>
                ) : null}
                {run.confidence !== null ? (
                  <span className="rounded-md border border-border-subtle bg-bg px-1.5 py-0.5 font-mono text-[9px] text-text-muted">
                    conf {run.confidence.toFixed(2)}
                  </span>
                ) : null}
                {run.parent_run_id ? (
                  <span className="rounded-md border border-accent/40 bg-bg px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-accent">
                    retro
                  </span>
                ) : null}
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  )
}
