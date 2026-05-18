'use client'

import { ArrowRight } from 'lucide-react'
import Link from 'next/link'
import { SectionCard } from '@/components/shared/SectionCard'
import type { BlendedCommittee } from '@/lib/api/signals'
import { cn } from '@/lib/utils'
import { NonDeterministicBadge } from './badges'

function relativeHours(iso: string | null): string {
  if (!iso) return ''
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const hours = (Date.now() - then) / (1000 * 60 * 60)
  if (hours < 1) return `${Math.max(1, Math.round(hours * 60))}m ago`
  if (hours < 24) return `${hours.toFixed(1)}h ago`
  return `${(hours / 24).toFixed(1)}d ago`
}

function cacheTtl(iso: string | null): { label: string; tone: string } {
  if (!iso) return { label: '—', tone: 'text-text-muted' }
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return { label: '—', tone: 'text-text-muted' }
  const hoursElapsed = (Date.now() - then) / (1000 * 60 * 60)
  const remaining = Math.max(0, 24 - hoursElapsed)
  if (remaining <= 0) {
    return { label: 'expired · next run eligible', tone: 'text-warning' }
  }
  return {
    label: `cached · ${remaining.toFixed(1)}h until next run`,
    tone: 'text-text-muted',
  }
}

const ACTION_TONE: Record<string, string> = {
  BUY: 'bg-success/20 text-success border-success/40',
  SELL: 'bg-danger/20 text-danger border-danger/40',
  HOLD: 'bg-warning/20 text-warning border-warning/40',
  TRIM: 'bg-warning/20 text-warning border-warning/40',
}

export function CommitteeLatestCard({
  committee,
  symbol,
}: {
  committee: BlendedCommittee | null
  symbol: string
}) {
  const actionKey = committee?.action?.toUpperCase() ?? ''
  const actionTone =
    ACTION_TONE[actionKey] ?? 'border-border-subtle bg-bg/40 text-text-muted'
  const ttl = cacheTtl(committee?.completedAt ?? null)
  const pmScore10 = committee ? committee.pmScore : null

  return (
    <SectionCard
      variant="surface"
      padding="md"
      title={
        <span className="inline-flex items-center gap-2">
          Committee verdict
          <NonDeterministicBadge />
        </span>
      }
      description={`Latest AI committee run for ${symbol}.`}
    >
      {committee ? (
        <div className="grid gap-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-2xl border border-border-subtle bg-bg/40 px-4 py-3">
              <div className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                Stance
              </div>
              <div className="mt-2 flex items-center gap-2">
                <span
                  className={cn(
                    'rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-[0.16em]',
                    actionTone,
                  )}
                >
                  {committee.action ?? '—'}
                </span>
                {committee.confidence != null ? (
                  <span className="font-mono text-xs text-text-muted">
                    conf {(committee.confidence * 100).toFixed(0)}%
                  </span>
                ) : null}
              </div>
            </div>
            <div className="rounded-2xl border border-border-subtle bg-bg/40 px-4 py-3">
              <div className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                PM score
              </div>
              <div className="mt-1 font-display italic text-2xl tabular-nums text-text">
                {pmScore10 !== null ? pmScore10.toFixed(1) : '—'}
                <span className="ml-1 text-xs text-text-muted">/ 10</span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-border-subtle bg-bg/40 px-4 py-3">
            <div className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
              Cache TTL
            </div>
            <p className={cn('mt-1 text-sm', ttl.tone)}>{ttl.label}</p>
            {committee.completedAt ? (
              <p className="mt-0.5 text-[11px] text-text-muted/80">
                Completed {relativeHours(committee.completedAt)}
                {committee.source ? ` · source: ${committee.source}` : ''}
                {committee.scannerRank != null
                  ? ` · scanner rank #${committee.scannerRank}`
                  : ''}
              </p>
            ) : null}
          </div>

          <Link
            href={`/portfolio/committee/${committee.runId}`}
            className="inline-flex items-center justify-between rounded-2xl border border-border-subtle bg-bg/40 px-4 py-3 text-sm text-text transition-colors hover:border-primary/40 hover:bg-surface/60"
          >
            <span>Open run · 6-stage breakdown</span>
            <ArrowRight className="h-4 w-4 text-text-muted" />
          </Link>
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-border-subtle bg-bg/30 px-4 py-6 text-center text-sm text-text-muted">
          No committee run on file for {symbol}. Trigger one from the Committee
          tab when ready.
        </div>
      )}
    </SectionCard>
  )
}
