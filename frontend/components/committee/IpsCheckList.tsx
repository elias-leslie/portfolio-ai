'use client'

import type { CommitteeUiState } from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'

const CHECK_LABELS: Record<string, string> = {
  concentration: 'Concentration',
  tax_bill: 'Tax bill',
  sector_exposure: 'Sector cap',
  wash_sale: 'Wash sale',
}

export function IpsCheckList({ state }: { state: CommitteeUiState }) {
  if (state.ips_checks.length === 0) {
    return (
      <div className="rounded-2xl border border-border-subtle bg-surface/40 p-4 text-center text-sm text-text-muted">
        IPS checks run after the trader proposes a trade.
      </div>
    )
  }
  return (
    <ul className="space-y-1.5">
      {state.ips_checks.map((check) => {
        const tone = check.passed
          ? 'text-gain border-gain/40 bg-gain/10'
          : check.severity === 'block'
            ? 'text-loss border-loss/40 bg-loss/10'
            : 'text-warning border-warning/40 bg-warning/10'
        return (
          <li
            key={check.name}
            className={cn('rounded-xl border px-3 py-2 text-sm', tone)}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="font-semibold uppercase tracking-[0.16em] text-text">
                {CHECK_LABELS[check.name] ?? check.name}
              </span>
              <span className="font-mono text-xs">
                {check.value !== null ? check.value.toFixed(3) : '—'}
                {check.threshold !== null
                  ? ` / ${check.threshold.toFixed(2)}`
                  : ''}
              </span>
            </div>
            <p className="mt-1 text-xs text-text-muted">{check.detail}</p>
          </li>
        )
      })}
    </ul>
  )
}
