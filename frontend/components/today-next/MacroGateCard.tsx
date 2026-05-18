import { ShieldAlert, ShieldCheck, ShieldQuestion } from 'lucide-react'
import { SectionCard } from '@/components/shared/SectionCard'
import type { MacroGate } from '@/lib/api/today-next'
import { cn } from '@/lib/utils'

const statusCopy: Record<string, { label: string; className: string }> = {
  risk_on: {
    label: 'Risk on',
    className: 'border-success/30 bg-success/10 text-success',
  },
  neutral: {
    label: 'Neutral',
    className: 'border-warning/30 bg-warning/10 text-warning',
  },
  risk_off: {
    label: 'Risk off',
    className: 'border-danger/30 bg-danger/10 text-danger',
  },
}

function GateIcon({ status }: { status: string }) {
  if (status === 'risk_on') return <ShieldCheck className="h-5 w-5" />
  if (status === 'risk_off') return <ShieldAlert className="h-5 w-5" />
  return <ShieldQuestion className="h-5 w-5" />
}

export function MacroGateCard({ macroGate }: { macroGate?: MacroGate }) {
  const status = macroGate ? statusCopy[macroGate.status] : undefined

  return (
    <SectionCard
      variant="surface"
      title="Macro gate"
      description="Market regime gate from health, fear/greed, volatility, and sector breadth."
      padding="md"
    >
      {macroGate ? (
        <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
          <div
            className={cn(
              'rounded-2xl border px-4 py-4',
              status?.className ?? 'border-border-subtle bg-surface text-text',
            )}
          >
            <div className="flex items-center gap-2 text-xs uppercase tracking-[0.18em]">
              <GateIcon status={macroGate.status} />
              {status?.label ?? macroGate.status}
            </div>
            <div className="mt-4 text-5xl font-semibold tracking-tight">
              {macroGate.score}
            </div>
            <div className="mt-1 text-sm text-text-muted">
              {macroGate.label}
            </div>
            <div className="mt-4 text-xs text-text-muted">
              Fear & Greed {macroGate.fearGreedScore} ·{' '}
              {macroGate.fearGreedLabel}
              {macroGate.vix ? ` · VIX ${macroGate.vix.toFixed(1)}` : ''}
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {macroGate.signals.map((signal) => (
              <div
                key={signal.label}
                className="rounded-xl border border-border-subtle bg-bg/40 px-4 py-3"
              >
                <div className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                  {signal.label}
                </div>
                <div className="mt-2 text-sm font-medium text-text">
                  {signal.value}
                </div>
                {typeof signal.score === 'number' ? (
                  <div className="mt-1 font-mono text-xs text-text-muted">
                    {Number.isInteger(signal.score)
                      ? signal.score
                      : signal.score.toFixed(2)}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-sm text-text-muted">Macro gate unavailable.</div>
      )}
    </SectionCard>
  )
}
