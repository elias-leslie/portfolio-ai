'use client'

import type { AgentState } from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'

const ANALYST_LABELS: Record<string, string> = {
  'fundamentals-v1': 'Fundamentals',
  'news-grounded-v1': 'News',
  'sentiment-grounded-v1': 'Sentiment',
  'technical-v1': 'Technical',
}

export function AnalystColumn({
  agents,
}: {
  agents: Record<string, AgentState>
}) {
  const analysts = Object.values(agents).filter((a) => a.role === 'analyst')
  if (analysts.length === 0) {
    return (
      <div className="rounded-2xl border border-border-subtle bg-surface/40 p-4 text-center text-sm text-text-muted">
        Awaiting analyst reports…
      </div>
    )
  }
  return (
    <div className="grid gap-2 lg:grid-cols-2">
      {analysts.map((agent) => (
        <article
          key={agent.slug}
          className="rounded-2xl border border-border-subtle bg-surface/40 p-3"
        >
          <header className="flex items-center justify-between gap-2">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted">
              {ANALYST_LABELS[agent.slug] ?? agent.slug}
            </p>
            <span
              className={cn(
                'font-mono text-xs',
                agent.score !== null && agent.score > 0
                  ? 'text-gain'
                  : agent.score !== null && agent.score < 0
                    ? 'text-loss'
                    : 'text-text-muted',
              )}
            >
              {agent.score !== null ? agent.score.toFixed(2) : '—'}
            </span>
          </header>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-text">
            {agent.content_md || <span className="text-text-muted/60">…</span>}
          </p>
        </article>
      ))}
    </div>
  )
}
