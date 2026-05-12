'use client'

import { useEffect, useRef } from 'react'
import type { CommitteeEvent } from '@/lib/committee/events'
import type { CommitteeUiState } from '@/lib/committee/reducer'
import { cn } from '@/lib/utils'

function formatTs(ts: string): string {
  const date = new Date(ts)
  if (Number.isNaN(date.getTime())) return ts.slice(11, 19)
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

function renderLine(event: CommitteeEvent): {
  glyph: string
  glyphClass: string
  body: React.ReactNode
} | null {
  const content = event.content as Record<string, unknown>
  switch (event.type) {
    case 'run.start':
      return {
        glyph: '▶',
        glyphClass: 'text-gain-strong',
        body: (
          <>
            graph=
            <b className="text-text">{String(content.graph_version ?? '')}</b>{' '}
            sym=<b className="text-text">{String(content.symbol ?? '')}</b>
          </>
        ),
      }
    case 'run.resume':
      return {
        glyph: '↻',
        glyphClass: 'text-primary',
        body: (
          <>
            resumed from=
            <b className="text-text">{String(content.resume_from ?? '')}</b>
          </>
        ),
      }
    case 'stage.enter':
      return {
        glyph: '⤴',
        glyphClass: 'text-primary',
        body: (
          <>
            stage=<b className="text-text">{event.stage ?? ''}</b>
          </>
        ),
      }
    case 'agent.start':
      return {
        glyph: '…',
        glyphClass: 'text-warning-strong',
        body: (
          <>
            <span className="text-accent">{event.agent_slug ?? '?'}</span> start
          </>
        ),
      }
    case 'agent.output':
      return {
        glyph: 'ok',
        glyphClass: 'text-gain-strong',
        body: (
          <>
            <span className="text-accent">{event.agent_slug ?? '?'}</span>{' '}
            {event.latency_ms ? `ms=${event.latency_ms}` : ''}{' '}
            {event.tokens ? `tok=${event.tokens}` : ''}{' '}
            {typeof event.score === 'number'
              ? `score=${event.score.toFixed(2)}`
              : ''}
          </>
        ),
      }
    case 'agent.error':
      return {
        glyph: '✕',
        glyphClass: 'text-loss-strong',
        body: (
          <>
            <span className="text-accent">{event.agent_slug ?? '?'}</span> error{' '}
            <span className="text-loss-strong">
              {String(content.error ?? '')}
            </span>
          </>
        ),
      }
    case 'debate.round.start':
      return {
        glyph: '◇',
        glyphClass: 'text-warning-strong',
        body: (
          <>
            debate round=
            <b className="text-text">{String(content.round ?? '')}</b> start
          </>
        ),
      }
    case 'debate.round.end':
      return {
        glyph: '◆',
        glyphClass: 'text-primary',
        body: (
          <>
            debate round=
            <b className="text-text">{String(content.round ?? '')}</b> bull=
            {String(content.bull_score ?? '')} bear=
            {String(content.bear_score ?? '')}
          </>
        ),
      }
    case 'ips.check':
      return {
        glyph: content.passed ? '✓' : '!',
        glyphClass: content.passed ? 'text-gain-strong' : 'text-loss-strong',
        body: (
          <>
            ips.{String(content.name ?? '')} {content.passed ? 'pass' : 'fail'}
          </>
        ),
      }
    case 'trader.proposal':
      return {
        glyph: '✎',
        glyphClass: 'text-accent',
        body: (
          <>
            proposal=<b className="text-text">{String(content.action ?? '')}</b>{' '}
            qty_pct={String(content.qty_pct ?? '')}
          </>
        ),
      }
    case 'risk.vote':
      return {
        glyph: '⚖',
        glyphClass: 'text-warning-strong',
        body: (
          <>
            risk <span className="text-accent">{event.agent_slug ?? '?'}</span>{' '}
            vote={String(content.vote ?? '')} score={String(event.score ?? '')}
          </>
        ),
      }
    case 'pm.decision':
      return {
        glyph: '★',
        glyphClass: 'text-gain-strong',
        body: (
          <>
            pm.decision=
            <b className="text-text">{String(content.action ?? '')}</b> conf=
            {String(content.confidence ?? '')}
          </>
        ),
      }
    case 'run.feedback.received':
      return {
        glyph: '💬',
        glyphClass: 'text-accent',
        body: (
          <>
            feedback round=
            <b className="text-text">{String(content.round ?? '')}</b> "
            {String(content.user_input ?? '').slice(0, 64)}…"
          </>
        ),
      }
    case 'run.feedback.resolved':
      return {
        glyph: '↺',
        glyphClass: content.decision_shifted
          ? 'text-warning-strong'
          : 'text-text-muted',
        body: (
          <>
            feedback round=
            <b className="text-text">{String(content.round ?? '')}</b> shifted=
            {String(Boolean(content.decision_shifted))}
          </>
        ),
      }
    case 'run.complete':
      return {
        glyph: '■',
        glyphClass: 'text-gain-strong',
        body: <>run.complete tokens={String(content.tokens_total ?? '')}</>,
      }
    case 'run.aborted':
      return {
        glyph: '⊘',
        glyphClass: 'text-loss-strong',
        body: <>run.aborted reason={String(content.reason ?? 'user')}</>,
      }
    case 'run.failed':
      return {
        glyph: '!',
        glyphClass: 'text-loss-strong',
        body: <>run.failed {String(content.error ?? '')}</>,
      }
    case 'kpi.tick':
      // Too noisy for the log — filter.
      return null
    default:
      return null
  }
}

export function ExecutionLog({ state }: { state: CommitteeUiState }) {
  const scrollerRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const el = scrollerRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [state.events.length])

  const lines = state.events
    .map((event) => ({ event, line: renderLine(event) }))
    .filter((entry) => entry.line !== null)

  const isLive = state.status === 'running' || state.status === 'pending'

  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-gradient-to-b from-surface to-bg">
      <div className="flex items-center justify-between border-b border-border-subtle px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] text-text-muted/70">
        <span>Execution log</span>
        <span
          className={cn(
            'inline-flex items-center gap-1.5 font-semibold',
            isLive ? 'text-gain-strong' : 'text-text-muted',
          )}
        >
          <span
            className={cn(
              'h-1.5 w-1.5 rounded-full bg-text-muted',
              isLive && 'animate-pulse bg-gain-strong',
            )}
          />
          {isLive ? 'tail -f' : 'closed'}
        </span>
      </div>
      <div
        ref={scrollerRef}
        className="max-h-[20rem] overflow-y-auto px-3 py-2 font-mono text-[11px] leading-relaxed"
      >
        {lines.length === 0 ? (
          <p className="text-text-muted/60">no events yet…</p>
        ) : (
          lines.map(({ event, line }) =>
            line ? (
              <div key={event.seq} className="flex items-baseline gap-2">
                <span className="text-text-muted/60">{formatTs(event.ts)}</span>
                <span className={line.glyphClass}>{line.glyph}</span>
                <span className="flex-1 text-text-muted">{line.body}</span>
              </div>
            ) : null,
          )
        )}
      </div>
    </div>
  )
}
