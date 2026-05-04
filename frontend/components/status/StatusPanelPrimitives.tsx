'use client'

export type SummaryStatTone = 'default' | 'positive' | 'warning' | 'negative'

const toneBorder: Record<SummaryStatTone, string> = {
  default: 'border-border/40',
  positive: 'border-gain/25 border-l-2 border-l-gain/50',
  warning: 'border-warning/25 border-l-2 border-l-warning/50',
  negative: 'border-loss/25 border-l-2 border-l-loss/50',
}

const toneValue: Record<SummaryStatTone, string> = {
  default: 'text-text group-hover:text-primary/90',
  positive: 'text-gain',
  warning: 'text-warning',
  negative: 'text-loss',
}

export function SummaryStat({
  label,
  value,
  detail,
  tone = 'default',
}: {
  label: string
  value: string
  detail: string
  tone?: SummaryStatTone
}) {
  return (
    <div
      className={`group rounded-2xl border ${toneBorder[tone]} bg-surface-muted/20 p-5 card-interactive hover:border-border/60 hover:bg-surface-muted/30`}
    >
      <p className="text-xs font-semibold uppercase tracking-widest text-text-muted">
        {label}
      </p>
      <p
        className={`mt-3 font-display italic text-2xl tabular-nums transition-colors ${toneValue[tone]}`}
      >
        {value}
      </p>
      <p className="mt-2 text-xs leading-relaxed text-text-muted">{detail}</p>
    </div>
  )
}

export function EmptyPanelMessage({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-border/50 bg-surface-muted/10 p-4 text-sm text-text-muted">
      {message}
    </div>
  )
}
