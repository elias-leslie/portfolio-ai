'use client'

import { ArrowRight, Sparkles, Zap } from 'lucide-react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import type { MacroSnapshot } from '@/lib/api/macro'
import { useMacroCurrent } from '@/lib/hooks/useSignals'
import { cn } from '@/lib/utils'
import { DeterministicBadge } from './badges'

interface ZoneStyle {
  label: string
  className: string
  pillClassName: string
  description: string
}

const ZONE_STYLES: Record<string, ZoneStyle> = {
  FULL_DEPLOY: {
    label: 'Full deploy',
    className:
      'border-success/40 bg-gradient-to-br from-success/15 via-success/5 to-transparent text-success',
    pillClassName: 'bg-success/20 text-success border-success/40',
    description: 'Conditions favor full risk allocation.',
  },
  REDUCED: {
    label: 'Reduced',
    className:
      'border-warning/40 bg-gradient-to-br from-warning/15 via-warning/5 to-transparent text-warning',
    pillClassName: 'bg-warning/20 text-warning border-warning/40',
    description: 'Trim or scan only top-quartile setups.',
  },
  DEFENSIVE: {
    label: 'Defensive',
    className:
      'border-danger/40 bg-gradient-to-br from-danger/15 via-danger/5 to-transparent text-danger',
    pillClassName: 'bg-danger/20 text-danger border-danger/40',
    description: 'Macro gate blocks new entries.',
  },
}

const COMPONENT_LABELS: Array<{
  key: keyof MacroSnapshot['components']
  label: string
}> = [
  { key: 'vix', label: 'VIX' },
  { key: 'term', label: 'Term' },
  { key: 'breadth', label: 'Breadth' },
  { key: 'credit', label: 'Credit' },
  { key: 'putcall', label: 'Put/Call' },
  { key: 'crowding', label: 'Crowding' },
]

function formatScore(value: number | null): string {
  if (value === null || value === undefined) return '—'
  return value.toFixed(0)
}

function ScoreBar({ value }: { value: number | null }) {
  const pct = value === null ? 0 : Math.max(0, Math.min(100, value))
  const tone =
    value === null
      ? 'bg-border-subtle'
      : pct >= 70
        ? 'bg-success/70'
        : pct >= 40
          ? 'bg-warning/70'
          : 'bg-danger/70'
  return (
    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-bg/60">
      <div
        className={cn('h-full rounded-full', tone)}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export function DeploymentZoneHero() {
  const { data, isLoading, error } = useMacroCurrent()

  const zoneKey = data?.zone?.toUpperCase()
  const zoneStyle: ZoneStyle = (zoneKey && ZONE_STYLES[zoneKey]) || {
    label: zoneKey ?? '—',
    className: 'border-border-subtle bg-surface/60 text-text-muted',
    pillClassName: 'bg-surface/60 text-text-muted border-border-subtle',
    description: 'Macro gate snapshot loading.',
  }

  const score = data?.deploymentScore ?? null
  const snapshotDate = data?.snapshotDate ?? null

  return (
    <section className="overflow-hidden rounded-2xl border border-border/40 bg-surface/50 backdrop-blur-sm">
      <div className="flex flex-col gap-3 border-b border-border-subtle/60 px-6 py-2.5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2.5">
          <Zap className="h-3.5 w-3.5 text-text-muted/70" />
          <h2 className="font-display italic text-base tracking-tight text-text">
            Deployment Zone
          </h2>
          <DeterministicBadge />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline" size="sm">
            <Link href="/portfolio?tab=signals">
              Open Signals tab
              <ArrowRight className="ml-1 h-3.5 w-3.5" />
            </Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href="/api/macro/backtest" target="_blank" rel="noreferrer">
              View backtest
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 px-6 py-5 lg:grid-cols-[minmax(280px,300px)_1fr]">
        <div
          className={cn(
            'flex flex-col justify-between rounded-2xl border px-5 py-5',
            zoneStyle.className,
          )}
        >
          <div className="flex items-center justify-between">
            <span
              className={cn(
                'rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em]',
                zoneStyle.pillClassName,
              )}
            >
              {zoneStyle.label}
            </span>
            {snapshotDate ? (
              <span className="text-[10px] uppercase tracking-[0.16em] text-current/70">
                {snapshotDate}
              </span>
            ) : null}
          </div>
          <div className="mt-4">
            <div className="flex items-baseline gap-2">
              <span className="font-display italic text-6xl tracking-tight tabular-nums">
                {score === null ? '—' : score.toFixed(0)}
              </span>
              <span className="text-sm text-current/70">/ 100</span>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-current/80">
              {zoneStyle.description}
            </p>
          </div>
          {data?.coverage != null ? (
            <div className="mt-4 flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-current/70">
              <Sparkles className="h-3 w-3" />
              Coverage {Math.round(data.coverage * 100)}%
            </div>
          ) : null}
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {COMPONENT_LABELS.map(({ key, label }) => {
            const value = data?.components?.[key] ?? null
            return (
              <div
                key={key}
                className="rounded-xl border border-border-subtle bg-bg/40 px-3 py-3"
              >
                <div className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                  {label}
                </div>
                <div className="mt-1.5 font-mono text-base tabular-nums text-text">
                  {formatScore(value)}
                </div>
                <ScoreBar value={value} />
              </div>
            )
          })}
        </div>
      </div>

      <div className="border-t border-border/40 bg-bg/30 px-6 py-2.5 text-[11px] text-text-muted">
        {error ? (
          <span className="text-danger">
            {error instanceof Error
              ? error.message
              : 'Macro gate snapshot unavailable.'}
          </span>
        ) : isLoading ? (
          <span>Loading macro gate snapshot…</span>
        ) : (
          <span>Next refresh after 17:30 ET</span>
        )}
      </div>
    </section>
  )
}
