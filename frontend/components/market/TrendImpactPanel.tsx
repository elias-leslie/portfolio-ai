'use client'

import { ChevronDown } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { cn } from '@/lib/utils'

export type ImpactTone = 'positive' | 'neutral' | 'warning' | 'negative'

export interface ImpactMetric {
  label: string
  value: string
  detail?: string
  tone?: ImpactTone
}

function toneClasses(tone: ImpactTone = 'neutral') {
  switch (tone) {
    case 'positive':
      return 'border-gain/35 bg-gain/8 text-gain'
    case 'warning':
      return 'border-warning/35 bg-warning/8 text-warning'
    case 'negative':
      return 'border-loss/35 bg-loss/8 text-loss'
    default:
      return 'border-border-subtle bg-bg/25 text-text'
  }
}

export function ImpactCard({
  eyebrow,
  title,
  summary,
  tone = 'neutral',
  metrics,
  footer,
  collapsed,
  onToggle,
}: {
  eyebrow: string
  title: string
  summary: string
  tone?: ImpactTone
  metrics?: ImpactMetric[]
  footer?: ReactNode
  collapsed: boolean
  onToggle: () => void
}) {
  if (collapsed) {
    return (
      <aside
        className={cn(
          'flex min-h-40 flex-row items-center justify-between gap-2 rounded-xl border px-3 py-3 lg:flex-col',
          toneClasses(tone),
        )}
      >
        <span className="rounded-full border border-current/30 px-2 py-0.5 text-[9px] font-bold uppercase tracking-[0.16em]">
          {eyebrow}
        </span>
        <p className="line-clamp-2 text-center text-xs font-semibold lg:[writing-mode:vertical-rl] lg:rotate-180">
          {title}
        </p>
        <button
          type="button"
          onClick={onToggle}
          className="rounded-full border border-current/30 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] hover:bg-current/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          aria-label={`Expand ${eyebrow} impact`}
        >
          Open
        </button>
      </aside>
    )
  }

  return (
    <aside
      className={cn('min-h-40 rounded-xl border px-4 py-3', toneClasses(tone))}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-current/70">
            {eyebrow}
          </p>
          <h4 className="mt-1 text-sm font-semibold leading-5 text-current">
            {title}
          </h4>
        </div>
        <button
          type="button"
          onClick={onToggle}
          className="rounded-full border border-current/25 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-current/80 hover:bg-current/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          aria-label={`Collapse ${eyebrow} impact`}
        >
          Min
        </button>
      </div>
      <p className="mt-3 text-xs leading-5 text-current/85">{summary}</p>
      {metrics?.length ? (
        <div className="mt-3 grid grid-cols-2 gap-2">
          {metrics.map((metric) => (
            <div
              key={metric.label}
              className="rounded-lg border border-current/15 bg-bg/20 px-2.5 py-2"
            >
              <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-current/60">
                {metric.label}
              </p>
              <p
                className={cn(
                  'mt-1 font-mono text-sm font-semibold tabular-nums text-current',
                  metric.tone === 'positive' && 'text-gain',
                  metric.tone === 'warning' && 'text-warning',
                  metric.tone === 'negative' && 'text-loss',
                )}
              >
                {metric.value}
              </p>
              {metric.detail ? (
                <p className="mt-0.5 text-[10px] leading-4 text-current/65">
                  {metric.detail}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
      {footer ? (
        <div className="mt-3 text-[10px] text-current/65">{footer}</div>
      ) : null}
    </aside>
  )
}

export function TrendImpactPanel({
  title,
  subtitle,
  controls,
  chart,
  impact,
  collapsed,
}: {
  title: string
  subtitle?: string
  controls?: ReactNode
  chart: ReactNode
  impact: ReactNode
  collapsed: boolean
}) {
  const [panelCollapsed, setPanelCollapsed] = useState(false)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="font-display italic text-lg tracking-tight text-text">
            {title}
          </h3>
          {subtitle ? (
            <p className="mt-1 text-[10px] uppercase tracking-[0.16em] text-text-muted">
              {subtitle}
            </p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {panelCollapsed ? null : controls}
          <button
            type="button"
            aria-expanded={!panelCollapsed}
            aria-label={
              panelCollapsed ? `Expand ${title}` : `Collapse ${title}`
            }
            onClick={() => setPanelCollapsed((value) => !value)}
            className="rounded-md p-1 text-text-muted transition-colors hover:bg-surface-muted/60 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            <ChevronDown
              className={cn(
                'h-4 w-4 transition-transform',
                panelCollapsed && '-rotate-90',
              )}
            />
          </button>
        </div>
      </div>
      {panelCollapsed ? null : (
        <div
          className={cn(
            'grid gap-4 lg:grid-cols-[minmax(0,1fr)_18rem]',
            collapsed && 'lg:grid-cols-[minmax(0,1fr)_5rem]',
          )}
        >
          <div>{chart}</div>
          {impact}
        </div>
      )}
    </div>
  )
}
