'use client'

import { ArrowDown, ArrowUp, ArrowUpDown, Search } from 'lucide-react'
import Link from 'next/link'
import { useMemo, useState } from 'react'
import type { BlendedRow } from '@/lib/api/signals'
import { cn } from '@/lib/utils'

const FACTOR_KEYS = [
  'mom_xover',
  'vol_surge',
  'rs_vs_spy',
  'high_52w_proximity',
  'short_interest_decline',
] as const

const FACTOR_LABELS: Record<(typeof FACTOR_KEYS)[number], string> = {
  mom_xover: 'Mom',
  vol_surge: 'Vol',
  rs_vs_spy: 'RS',
  high_52w_proximity: '52wH',
  short_interest_decline: 'SI↓',
}

const FACTOR_CAMEL_KEYS: Record<(typeof FACTOR_KEYS)[number], string> = {
  mom_xover: 'momXover',
  vol_surge: 'volSurge',
  rs_vs_spy: 'rsVsSpy',
  high_52w_proximity: 'high52wProximity',
  short_interest_decline: 'shortInterestDecline',
}

type SortKey =
  | 'blendedRank'
  | 'scannerRank'
  | 'deltaRank'
  | 'symbol'
  | 'scannerCompositePct'
  | 'committeePct'
  | 'blendedScore'

interface ScannerTableProps {
  rows: BlendedRow[]
  /** Per-symbol factor percentiles, keyed by symbol → { factor_key: 0-100 }. */
  factorPercentilesBySymbol?: Record<string, Record<string, number | null>>
  /** Compact mode used by /portfolio Signals tab. */
  compact?: boolean
}

function FactorBar({ value }: { value: number | null }) {
  if (value === null || value === undefined) {
    return <span className="text-[10px] text-text-muted/60">—</span>
  }
  const pct = Math.max(0, Math.min(100, value))
  const tone =
    pct >= 70 ? 'bg-success/70' : pct >= 40 ? 'bg-warning/70' : 'bg-danger/70'
  return (
    <div
      className="relative h-1.5 w-12 overflow-hidden rounded-full bg-bg/60"
      title={`${pct.toFixed(0)} percentile`}
    >
      <div
        className={cn('h-full rounded-full', tone)}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

function factorPercentile(
  percentiles: Record<string, number | null> | undefined,
  key: (typeof FACTOR_KEYS)[number],
): number | null {
  return percentiles?.[key] ?? percentiles?.[FACTOR_CAMEL_KEYS[key]] ?? null
}

function SortHeader({
  label,
  current,
  direction,
  thisKey,
  onSort,
  align = 'left',
  className,
}: {
  label: string
  current: SortKey
  direction: 'asc' | 'desc'
  thisKey: SortKey
  onSort: (key: SortKey) => void
  align?: 'left' | 'right'
  className?: string
}) {
  const active = current === thisKey
  return (
    <th
      className={cn(
        'px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted',
        align === 'right' ? 'text-right' : 'text-left',
        className,
      )}
    >
      <button
        type="button"
        onClick={() => onSort(thisKey)}
        className={cn(
          'inline-flex items-center gap-1 hover:text-text',
          align === 'right' && 'flex-row-reverse',
          active && 'text-text',
        )}
      >
        {label}
        {active ? (
          direction === 'asc' ? (
            <ArrowUp className="h-3 w-3" />
          ) : (
            <ArrowDown className="h-3 w-3" />
          )
        ) : (
          <ArrowUpDown className="h-3 w-3 opacity-50" />
        )}
      </button>
    </th>
  )
}

export function ScannerTable({
  rows,
  factorPercentilesBySymbol,
  compact = false,
}: ScannerTableProps) {
  const [sort, setSort] = useState<{ key: SortKey; direction: 'asc' | 'desc' }>(
    { key: 'blendedRank', direction: 'asc' },
  )
  const [query, setQuery] = useState('')

  const handleSort = (key: SortKey) => {
    setSort((prev) =>
      prev.key === key
        ? { key, direction: prev.direction === 'asc' ? 'desc' : 'asc' }
        : { key, direction: key === 'symbol' ? 'asc' : 'asc' },
    )
  }

  const filtered = useMemo(() => {
    const q = query.trim().toUpperCase()
    if (!q) return rows
    return rows.filter((r) => r.symbol.includes(q))
  }, [rows, query])

  const sorted = useMemo(() => {
    const cmp = (a: BlendedRow, b: BlendedRow): number => {
      switch (sort.key) {
        case 'symbol':
          return a.symbol.localeCompare(b.symbol)
        case 'blendedRank':
          return a.blendedRank - b.blendedRank
        case 'scannerRank':
          return a.scannerRank - b.scannerRank
        case 'deltaRank':
          return a.deltaRank - b.deltaRank
        case 'scannerCompositePct':
          return a.scannerCompositePct - b.scannerCompositePct
        case 'committeePct': {
          const av = a.committee?.pmScore ?? -1
          const bv = b.committee?.pmScore ?? -1
          return av - bv
        }
        case 'blendedScore':
          return a.blendedScore - b.blendedScore
      }
    }
    const out = [...filtered].sort(cmp)
    return sort.direction === 'desc' ? out.reverse() : out
  }, [filtered, sort])

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter symbol…"
            className="w-full rounded-xl border border-border-subtle bg-surface/60 py-1.5 pl-8 pr-3 text-sm uppercase tracking-[0.12em] text-text placeholder:text-text-muted/60 focus:outline-none focus:ring-1 focus:ring-primary/40"
          />
        </div>
        <span className="text-xs text-text-muted">
          {sorted.length} of {rows.length} rows
        </span>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-border-subtle">
        <table className="min-w-full divide-y divide-border-subtle text-sm">
          <thead className="bg-bg/40">
            <tr>
              <SortHeader
                label="#"
                current={sort.key}
                direction={sort.direction}
                thisKey="blendedRank"
                onSort={handleSort}
                align="right"
              />
              <SortHeader
                label="Δ"
                current={sort.key}
                direction={sort.direction}
                thisKey="deltaRank"
                onSort={handleSort}
                align="right"
              />
              <SortHeader
                label="Symbol"
                current={sort.key}
                direction={sort.direction}
                thisKey="symbol"
                onSort={handleSort}
              />
              {!compact ? (
                <th
                  className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.16em] text-text-muted"
                  colSpan={FACTOR_KEYS.length}
                >
                  Factors
                </th>
              ) : null}
              <SortHeader
                label="Comp %"
                current={sort.key}
                direction={sort.direction}
                thisKey="scannerCompositePct"
                onSort={handleSort}
                align="right"
              />
              <SortHeader
                label="Cmte"
                current={sort.key}
                direction={sort.direction}
                thisKey="committeePct"
                onSort={handleSort}
                align="right"
              />
              <SortHeader
                label="Blended"
                current={sort.key}
                direction={sort.direction}
                thisKey="blendedScore"
                onSort={handleSort}
                align="right"
              />
            </tr>
            {!compact ? (
              <tr className="bg-bg/30">
                <th colSpan={3} />
                {FACTOR_KEYS.map((key) => (
                  <th
                    key={key}
                    className="px-2 py-1 text-center text-[10px] font-medium uppercase tracking-[0.12em] text-text-muted/70"
                  >
                    {FACTOR_LABELS[key]}
                  </th>
                ))}
                <th colSpan={3} />
              </tr>
            ) : null}
          </thead>
          <tbody className="divide-y divide-border-subtle">
            {sorted.map((row) => {
              const pcts = factorPercentilesBySymbol?.[row.symbol]
              return (
                <tr
                  key={row.symbol}
                  className={cn(
                    'transition-colors hover:bg-surface/60',
                    row.flagged &&
                      (row.deltaRank > 0 ? 'bg-success/5' : 'bg-danger/5'),
                  )}
                >
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums text-text">
                    {row.blendedRank}
                  </td>
                  <td
                    className={cn(
                      'px-3 py-2.5 text-right font-mono tabular-nums',
                      row.flagged
                        ? row.deltaRank > 0
                          ? 'text-success'
                          : 'text-danger'
                        : 'text-text-muted',
                    )}
                  >
                    {row.deltaRank > 0 ? '+' : ''}
                    {row.deltaRank}
                  </td>
                  <td className="px-3 py-2.5">
                    <Link
                      href={`/symbols/${row.symbol}`}
                      className="font-mono font-semibold text-primary hover:underline"
                    >
                      {row.symbol}
                    </Link>
                  </td>
                  {!compact
                    ? FACTOR_KEYS.map((key) => (
                        <td key={key} className="px-2 py-2.5">
                          <FactorBar value={factorPercentile(pcts, key)} />
                        </td>
                      ))
                    : null}
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums text-text">
                    {row.scannerCompositePct.toFixed(1)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums text-text-muted">
                    {row.committee
                      ? (row.committee.pmScore * 10).toFixed(0)
                      : '—'}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono tabular-nums font-semibold text-text">
                    {row.blendedScore.toFixed(1)}
                  </td>
                </tr>
              )
            })}
            {sorted.length === 0 ? (
              <tr>
                <td
                  colSpan={compact ? 6 : 11}
                  className="px-3 py-8 text-center text-sm text-text-muted"
                >
                  {rows.length === 0
                    ? 'No scanner candidates (gate may be defensive).'
                    : 'No symbols match the filter.'}
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  )
}
