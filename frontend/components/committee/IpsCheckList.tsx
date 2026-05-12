'use client'

import type { CommitteeUiState } from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'

const CHECK_LABELS: Record<string, string> = {
  concentration: 'Concentration',
  tax_bill: 'Tax bill',
  sector_exposure: 'Sector exposure',
  wash_sale: 'Wash sale',
}

export function IpsCheckList({ state }: { state: CommitteeUiState }) {
  const allPass =
    state.ips_checks.length > 0 && state.ips_checks.every((c) => c.passed)
  const anyBlock = state.ips_checks.some(
    (c) => !c.passed && c.severity === 'block',
  )

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-gradient-to-b from-surface to-bg">
      <div className="flex items-center justify-between border-b border-border-subtle px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] text-text-muted/70">
        <span>IPS &amp; risk checks</span>
        {state.ips_checks.length === 0 ? (
          <span className="text-text-muted">pending</span>
        ) : allPass ? (
          <span className="text-gain-strong">pass</span>
        ) : anyBlock ? (
          <span className="text-loss-strong">blocked</span>
        ) : (
          <span className="text-warning-strong">warn</span>
        )}
      </div>
      <div className="px-3 py-2.5 text-[12px] leading-[1.7] text-text-muted">
        {state.ips_checks.length === 0 ? (
          <p className="text-text-muted/60">
            checks run after the trader proposes…
          </p>
        ) : (
          state.ips_checks.map((check, idx) => {
            const valueLabel =
              check.value !== null && Number.isFinite(check.value)
                ? check.value.toFixed(3)
                : check.passed
                  ? 'ok'
                  : 'fail'
            const tone = check.passed
              ? 'text-gain-strong'
              : check.severity === 'block'
                ? 'text-loss-strong'
                : 'text-warning-strong'
            return (
              <div key={`${check.name}-${idx}`} className="py-0.5">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-text-muted">
                    {CHECK_LABELS[check.name] ?? check.name}:
                  </span>
                  <span className={cn('font-mono text-[11px]', tone)}>
                    {valueLabel}
                    {check.threshold !== null && check.threshold !== undefined
                      ? ` / ${check.threshold.toFixed(2)}`
                      : ''}{' '}
                    {check.passed ? '✓' : '✕'}
                  </span>
                </div>
                {check.detail ? (
                  <p className="text-[10px] text-text-muted/70">
                    {check.detail}
                  </p>
                ) : null}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
