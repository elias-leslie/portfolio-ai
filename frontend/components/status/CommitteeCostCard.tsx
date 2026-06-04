'use client'

import { useEffect, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { type CommitteeCostDay, fetchCommitteeCost } from '@/lib/api/committee'

const SPARK_W = 140
const SPARK_H = 36

export function CommitteeCostCard() {
  const [days, setDays] = useState<CommitteeCostDay[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchCommitteeCost(7)
      .then((res) => {
        if (!cancelled) setDays(res.days)
      })
      .catch((err) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : String(err))
      })
    return () => {
      cancelled = true
    }
  }, [])

  const today = days[days.length - 1] ?? null
  const max = Math.max(1, ...days.map((d) => d.estCostUsd))
  const points = days
    .map((d, i) => {
      const x = (i / Math.max(1, days.length - 1)) * SPARK_W
      const y = SPARK_H - (d.estCostUsd / max) * SPARK_H
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  return (
    <SectionCard variant="surface" padding="md" title="Committee cost">
      {error ? (
        <div className="text-sm text-danger">
          cost endpoint unavailable: {error}
        </div>
      ) : (
        <div className="grid gap-4">
          <div className="grid gap-3">
            <Counter label="Runs" value={today?.runCount ?? 0} suffix="runs" />
          </div>
          <div className="flex items-end justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                Today
              </div>
              <div className="mt-1 text-2xl font-semibold">
                {formatUsd(today?.estCostUsd ?? 0)}
              </div>
              <div className="text-xs text-text-muted">
                {(today?.totalTokens ?? 0).toLocaleString()} tokens
              </div>
            </div>
            {days.length > 0 ? (
              <svg
                width={SPARK_W}
                height={SPARK_H}
                viewBox={`0 0 ${SPARK_W} ${SPARK_H}`}
                role="img"
                aria-label="7-day committee cost sparkline"
                className="opacity-80"
              >
                <polyline
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  points={points}
                />
              </svg>
            ) : null}
          </div>
        </div>
      )}
    </SectionCard>
  )
}

function Counter({
  label,
  value,
  suffix,
}: {
  label: string
  value: number
  suffix: string
}) {
  return (
    <div className="rounded-2xl border border-border-subtle bg-bg/40 px-4 py-3">
      <div className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
        {label}
      </div>
      <div className="mt-1 text-lg font-semibold">
        {value.toLocaleString()}{' '}
        <span className="text-xs font-normal text-text-muted">{suffix}</span>
      </div>
    </div>
  )
}

function formatUsd(n: number): string {
  if (n >= 10) return `$${n.toFixed(2)}`
  if (n >= 1) return `$${n.toFixed(3)}`
  return `$${n.toFixed(4)}`
}
