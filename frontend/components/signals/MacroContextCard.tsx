'use client'

import { SectionCard } from '@/components/shared/SectionCard'
import type { MacroContext, SymbolScannerRow } from '@/lib/api/signals'
import { cn } from '@/lib/utils'
import { DeterministicBadge } from './badges'

const ZONE_CLASSES: Record<string, string> = {
  FULL_DEPLOY: 'bg-success/20 text-success border-success/40',
  REDUCED: 'bg-warning/20 text-warning border-warning/40',
  DEFENSIVE: 'bg-danger/20 text-danger border-danger/40',
}

const COMPONENT_ROWS: Array<{
  key: keyof MacroContext['components']
  label: string
}> = [
  { key: 'vix', label: 'VIX' },
  { key: 'term', label: 'Term' },
  { key: 'breadth', label: 'Breadth' },
  { key: 'credit', label: 'Credit' },
  { key: 'putcall', label: 'Put/Call' },
  { key: 'crowding', label: 'Crowding' },
]

function fmtScore(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return v.toFixed(0)
}

export function MacroContextCard({
  macro,
  scanner,
  symbol,
}: {
  macro: MacroContext
  scanner: SymbolScannerRow[]
  symbol: string
}) {
  const zoneKey = macro.zone?.toUpperCase() ?? ''
  const zoneClass =
    ZONE_CLASSES[zoneKey] ??
    'border-border-subtle bg-surface/60 text-text-muted'

  const latest = scanner[0] ?? null
  const previous = scanner[1] ?? null
  const rankDelta =
    latest && previous
      ? previous.rank - latest.rank // positive = improved (lower rank number is better)
      : null

  return (
    <SectionCard
      variant="surface"
      padding="md"
      title={
        <span className="inline-flex items-center gap-2">
          Macro context
          <DeterministicBadge />
        </span>
      }
      description={`How the L1 gate and L2 scanner see ${symbol} right now.`}
    >
      <div className="grid gap-4">
        <div className="flex items-center justify-between rounded-2xl border border-border-subtle bg-bg/40 px-4 py-3">
          <div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
              Deployment zone
            </div>
            <div className="mt-1 flex items-center gap-2">
              <span
                className={cn(
                  'rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em]',
                  zoneClass,
                )}
              >
                {macro.zone ?? '—'}
              </span>
              {macro.snapshotDate ? (
                <span className="text-[10px] text-text-muted">
                  {macro.snapshotDate}
                </span>
              ) : null}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
              Score
            </div>
            <div className="mt-1 font-display italic text-2xl tabular-nums text-text">
              {fmtScore(macro.deploymentScore)}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          {COMPONENT_ROWS.map(({ key, label }) => (
            <div
              key={key}
              className="rounded-xl border border-border-subtle bg-bg/40 px-3 py-2"
            >
              <div className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                {label}
              </div>
              <div className="mt-1 font-mono text-sm tabular-nums text-text">
                {fmtScore(macro.components[key])}
              </div>
            </div>
          ))}
        </div>

        <div className="rounded-2xl border border-border-subtle bg-bg/40 px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
              Scanner rank
            </div>
            {rankDelta !== null && rankDelta !== 0 ? (
              <span
                className={cn(
                  'rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em]',
                  rankDelta > 0
                    ? 'bg-success/20 text-success'
                    : 'bg-danger/20 text-danger',
                )}
                title="Change vs. prior scanner run"
              >
                {rankDelta > 0 ? '▲' : '▼'} {Math.abs(rankDelta)}
              </span>
            ) : null}
          </div>
          {latest ? (
            <div className="mt-2 flex items-baseline gap-3">
              <span className="font-mono text-2xl tabular-nums text-text">
                #{latest.rank}
              </span>
              <span className="text-sm text-text-muted">
                composite{' '}
                <span className="font-mono text-text">
                  {latest.compositePct?.toFixed(1) ?? '—'}
                </span>
              </span>
              <span className="text-xs text-text-muted">
                · {latest.runDate} · {latest.gateZone}
              </span>
            </div>
          ) : (
            <p className="mt-1 text-xs text-text-muted">
              No scanner history yet — symbol may be off-universe or gate is
              defensive.
            </p>
          )}
        </div>
      </div>
    </SectionCard>
  )
}
